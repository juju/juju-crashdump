import subprocess
import tempfile
import shutil
import shlex
import yaml
import sys
import os
import glob

LOCAL = 'local'
REMOTE = 'remote'
ADDONS_FILE_PATH = os.path.join(os.path.dirname(__file__), 'addons.yaml')
FNULL = open(os.devnull, 'w')


def do_addons(addons_file_path, enabled_addons, units, uniq):
    push_location = '/tmp/{uniq}/addons'.format(uniq=uniq)
    pull_location = '/tmp/{uniq}/addon_output'.format(uniq=uniq)
    addons = {}
    for addon_file in addons_file_path:
        addons.update(load_addons(addon_file))
    if enabled_addons:
        async_commands('juju ssh {} "mkdir -p %s"' % push_location, units)
        async_commands('juju ssh {} "mkdir -p %s"' % pull_location, units)
    for addon in enabled_addons:
        if addon not in addons:
            print('The addons file: "%s" does not define %s' %
                  (addons_file_path, addon))
            sys.exit(1)
        addons[addon].push(units, push_location)
        addons[addon].run(units,
                          {'location': push_location, 'output': pull_location})


def tempdir(func):
    def temp_function(*args, **kwargs):
        olddir = os.getcwd()
        tempdir = tempfile.mkdtemp()
        os.chdir(tempdir)
        func(*args, **kwargs)
        os.chdir(olddir)
        shutil.rmtree(tempdir)
    return temp_function


def load_addons(addons_file_path):
    with open(addons_file_path) as addons_file:
        addon_specs = yaml.load(addons_file)
    addons = {}
    for name, info in addon_specs.items():
        try:
            assert(LOCAL in info)
            assert(REMOTE in info)
        except AssertionError:
            print('The addons file: "%s" is malformed, "%s" does not have one'
                  ' of the necessary keys "%s" or "%s"' %
                  (addons_file_path, name, LOCAL, REMOTE))
            sys.exit(1)
        addons[name] = CrashdumpAddon(name, info[LOCAL], info[REMOTE])
    return addons


def async_commands(command, contexts, timeout=45):
    """Run the command concurrently for each given context."""
    procs = []
    for context in contexts:
        args = shlex.split(('timeout %ds ' % timeout) +
                           command.format(context))
        procs.append(subprocess.Popen(args, stdin=FNULL, stdout=FNULL,
                                      stderr=FNULL))
    for proc in procs:
        proc.communicate()
        if proc.returncode != 0:
            print('command %s failed' % command)


class CrashdumpAddon(object):
    """An addon to run on the nodes"""
    def __init__(self, name, local, remote):
        self.name = name
        self.local = local
        self.remote = remote

    @tempdir
    def push(self, units, location):
        """This will fetch the command, and push it to the units"""
        subprocess.check_call(self.local, shell=True, stdout=FNULL,
                              stderr=FNULL)
        files = ' '.join(glob.glob('*'))
        async_commands('juju scp -- -r  %s {}:%s' % (files, location), units)

    def run(self, units, context):
        """This will runt the remote command on the units"""
        remote_cmd = '"cd {location}; %s"' % self.remote.format(**context)
        remote_cmd = remote_cmd.format(**context)
        async_commands('juju ssh {} -- %s' % remote_cmd, units)
