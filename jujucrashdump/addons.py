import subprocess
import tempfile
import shutil
import shlex
import yaml
import sys
import os
import glob
import logging
from string import Formatter

ADDONS_FILE_PATH = os.path.join(os.path.dirname(__file__), "addons.yaml")
FNULL = open(os.devnull, "w")


def do_addons(
    addons_file_path, enabled_addons, machines, units, dump_to, uniq, as_root
):
    push_location = "/{dump_to}/{uniq}/addons".format(dump_to=dump_to, uniq=uniq)
    pull_location = "/{dump_to}/{uniq}/addon_output".format(dump_to=dump_to, uniq=uniq)
    addons = {}
    machines = [{"machine": m} for m in machines]
    units = [{"unit": u} for u in units]
    for addon_file in addons_file_path:
        addons.update(load_addons(addon_file, enabled_addons, as_root))
    async_commands('juju ssh {machine} "mkdir -p %s"' % push_location, machines)
    async_commands('juju ssh {machine} "mkdir -p %s"' % pull_location, machines)
    for addon in enabled_addons:
        if addon not in addons:
            logging.warning(
                'The addons file: "%s" does not define %s' % (addons_file_path, addon)
            )
            sys.exit(1)
        addons[addon].run(
            machines, units, {"location": push_location, "output": pull_location}
        )
    return pull_location


def tempdir(func):
    def temp_function(*args, **kwargs):
        olddir = os.getcwd()
        tempdir = tempfile.mkdtemp()
        os.chdir(tempdir)
        func(*args, **kwargs)
        os.chdir(olddir)
        shutil.rmtree(tempdir)

    return temp_function


def load_addons(addons_file_path, enabled_addons, as_root):
    with open(addons_file_path) as addons_file:
        addon_specs = yaml.safe_load(addons_file)
    addons = {}
    for name, info in addon_specs.items():
        if name not in enabled_addons:
            continue
        # Do not allow remote commands using sudo or any local command if as_root==False
        if (
            "sudo" in " ".join(info.values())
            or any(k.startswith("local") for k in list(info))
        ) and not as_root:
            logging.warn("The as_root flag must be used to run addon %s" % name)
            enabled_addons.remove(name)
            continue
        addons[name] = CrashdumpAddon(name, info)
    return addons


def async_commands(command, contexts, timeout=45, shell=False):
    """Run the command concurrently for each given context."""
    procs = []
    for context in contexts:
        args = ("timeout %ds " % timeout) + command.format(**context)
        if not shell:
            args = shlex.split(args)
        logging.debug("Running {} in context {}".format(command, context))
        procs.append(
            [
                subprocess.Popen(
                    args, stdin=FNULL, stdout=FNULL, stderr=FNULL, shell=shell
                ),
                args,
            ]
        )
    for proc in procs:
        proc[0].communicate()
        if proc[0].returncode != 0:
            logging.warning("command %s failed" % proc[1])


class CrashdumpAddon(object):
    """An addon to run on the nodes"""

    def __init__(self, name, info={}):
        self.name = name
        self.info = info

    def run(self, machines, units, context):
        for action, command in self.info.items():
            try:
                getattr(self, action.replace("-", "_"))(
                    machines, units, context, command
                )
            except AttributeError:
                logging.warn("Invalid action: %s" % action)
                raise

    def local(self, machines, units, context, command):
        """This will fetch the command, and push it to the machines"""
        subprocess.check_call(command, shell=True, stdout=FNULL, stderr=FNULL)
        files = " ".join(glob.glob("*"))
        async_commands(
            "juju scp -- -r  %s {machine}:%s" % (files, context["location"]), machines
        )

    def local_per_unit(self, machines, units, context, cmd):
        # Check if {unit} or {machine} is used and update the command to push to the
        # juju machine accordingly.
        fields = list({f for _, f, _, _ in Formatter().parse(cmd) if f} - set(context))
        if len(fields) > 1 or not fields[0] in ["machine", "unit"]:
            raise ValueError("Invalid fields for local-per-unit: %s" % fields)
        command = (
            "{cmd} | juju ssh {field} 'mkdir {output}/{name}; "
            "cat > {output}/{name}/$(echo {field} | tr / _)'"
        ).format(cmd=cmd, name=self.name, field="{%s}" % fields[0], **context)
        async_commands(command, vars()["%ss" % fields[0]], shell=True)

    def remote(self, machines, units, context, command):
        """This will runt the remote command on the machines"""
        remote_cmd = '"cd {location}; %s"' % command.format(**context)
        remote_cmd = remote_cmd.format(**context)
        async_commands("juju ssh {machine} -- %s" % remote_cmd, machines)
