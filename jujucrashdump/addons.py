import subprocess
import tempfile
import shutil
import shlex
import yaml
import sys
import os

FETCH = 'local'
RUN = 'remote'
ADDONS_FILE_PATH = os.path.join(os.path.dirname(__file__), 'addons.yaml')
FNULL = open(os.devnull, 'w')


def do_addons(addons_file_path, enabled_addons, units, uniq):
    push_location = '/tmp/{uniq}/addons'.format(uniq=uniq)
    pull_location = '/tmp/{uniq}/addon_output'.format(uniq=uniq)
    addons = load_addons(addons_file_path)
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
            assert(FETCH in info)
            assert(RUN in info)
        except AssertionError:
            print('The addons file: "%s" is malformed, "%s" does not have one'
                  ' of the necessary keys "%s" or "%s"' %
                  (addons_file_path, name, FETCH, RUN))
            sys.exit(1)
        addons[name] = CrashdumpAddon(name, info[FETCH], info[RUN])
    return addons


def async_commands(command, contexts, timeout=10):
    """Run the command concurrently for each given context."""
    procs = []
    for context in contexts:
        args = shlex.split(command.format(context))
        procs.append(subprocess.Popen(args, stdout=FNULL, stderr=FNULL))
    for proc in procs:
        value = proc.wait()
        if value != 0:
            print('command %s failed' % command)


class CrashdumpAddon(object):
    """An addon to run on the nodes"""
    def __init__(self, name, fetch, run):
        self.name = name
        self.fetch = fetch
        self.run_cmd = run

    @tempdir
    def push(self, units, location):
        """This will fetch the command, and push it to the units"""
        subprocess.check_call(self.fetch, shell=True, stdout=FNULL,
                              stderr=FNULL)
        async_commands('juju scp -- -r . {}:%s' % location, units)

    @tempdir
    def run(self, units, context):
        """This will runt the remote command on the units"""
        remote_cmd = '"cd {location}; %s"' % self.run_cmd.format(**context)
        remote_cmd = remote_cmd.format(**context)
        async_commands('juju ssh {} -- %s' % remote_cmd, units)
