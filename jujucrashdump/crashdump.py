#!/usr/bin/env python2
# this is python2/3 compatible, but the following bug breaks us...
# https://bugs.launchpad.net/ubuntu/+source/python-launchpadlib/+bug/1425575

# you also might need to $ sudo apt install python-apport

import argparse
import functools
import multiprocessing
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
import yaml
from collections import defaultdict
from os.path import expanduser
try:
    import apport
    import apport.crashdb
    import apport.hookutils
    APPORT = True
except ImportError:
    APPORT = False

from textwrap import dedent
from jujucrashdump.addons import ADDONS_FILE_PATH, do_addons, FNULL


MAX_FILE_SIZE = 5000000  # 5MB max for files
DIRECTORIES = [
    # '/var/lib/juju',  # Added below, if --small not passed.
    '/var/log',
    '/etc/ceph',
    '/etc/cinder',
    '/etc/glance',
    '/etc/keystone',
    '/etc/neutron',
    '/etc/nova',
    '/etc/quantum',
    '/etc/swift',
    '/opt/nedge/var/log',
    '/usr/share/lxc/config',
    '/var/lib/libvirt/filesystems/plumgrid-data/log',
    '/var/lib/libvirt/filesystems/plumgrid/var/log',
]

TAR_CMD = """sudo find {dirs} -mount -type f -size -{max_size}c -o \
-size {max_size}c 2>/dev/null | sudo tar -pcf /tmp/juju-dump-{uniq}.tar \
--files-from - 2>/dev/null; sudo tar --append -f /tmp/juju-dump-{uniq}.tar \
-C /tmp/{uniq}/addon_output . || true"""


def service_unit_addresses(status):
    """From a given juju_status.yaml dict return a mapping of
    {'machine/container': ['<service1>', '<service2>', '<ip>']}."""
    out = defaultdict(set)
    ip_to_machine = dict()
    for m_id, m_info in status['machines'].items():
        if 'dns-name' not in m_info:
            continue
        out[m_id].add(m_info['dns-name'])
        ip_to_machine[m_info['dns-name']] = m_id
        for c_id, c_info in m_info.get('containers', {}).items():
            if 'dns-name' not in c_info:
                continue
            out[c_id].add(c_info['dns-name'])
            ip_to_machine[c_info['dns-name']] = c_id

    for _, a_info in status['applications'].items():
        if 'subordinate-to' in a_info:
            continue
        for u_id, u_info in a_info.get('units', {}).items():
            if 'public-address' not in u_info:
                continue
            machine = ip_to_machine[u_info['public-address']]
            out[machine].add(u_id)
            if 'subordinates' in u_info:
                for s_id, s_info in u_info['subordinates'].items():
                    if 'public-address' not in s_info:
                        continue
                    machine = ip_to_machine[s_info['public-address']]
                    out[machine].add(s_id)

    return out


def set_model(model):
    os.environ['JUJU_ENV'] = model
    os.environ['JUJU_MODEL'] = model


def run_cmd(command, fatal=False, to_file=None):
    try:
        output = subprocess.check_output(command, shell=True, stderr=FNULL)
        if to_file is not None:
            with open(to_file, 'wb') as fd:
                fd.write(output)
    except:
        print('Command "%s" failed' % command)
        if fatal:
            sys.exit(1)


def juju_cmd(command, *args, **kwargs):
    command_prefix = 'juju '
    run_cmd(command_prefix + command, *args, **kwargs)


def juju_check():
    run_cmd('juju version', fatal=True)
    run_cmd('juju switch', fatal=True)


def juju_status():
    juju_cmd(' status --format=yaml', to_file='juju_status.yaml')


def juju_debuglog():
    juju_cmd('debug-log --replay --no-tail', to_file='debug_log.txt')


class CrashCollector(object):
    """A log file collector for juju and charms"""
    def __init__(self, model, max_size, extra_dirs, output_dir=None,
                 uniq=None, addons=None, addons_file=None, exclude=tuple()):
        if model:
            set_model(model)
        self.max_size = max_size
        self.extra_dirs = extra_dirs
        self.cwd = os.getcwd()
        self.tempdir = tempfile.mkdtemp(dir=expanduser('~'))
        os.chdir(self.tempdir)
        self.uniq = uniq or uuid.uuid4()
        self.output_dir = output_dir or '.'
        self.addons = addons
        self.addons_file = addons_file
        self.exclude = exclude

    def run_addons(self):
        juju_status = yaml.load(open('juju_status.yaml', 'r'))
        machines = service_unit_addresses(juju_status).keys()
        if not machines:
            return
        if self.addons_file is None or self.addons is None:
            return do_addons(self.addons_file, self.addons, machines,
                             self.uniq)

    def create_unit_tarballs(self):
        directories = list(DIRECTORIES)
        directories.extend(self.extra_dirs)
        directories.extend(
            ['/var/lib/lxd/containers/*/rootfs' + item for item in directories]
        )
        tar_cmd = TAR_CMD.format(dirs=" ".join(directories),
                                 max_size=self.max_size, uniq=self.uniq)
        run_cmd("""timeout 30s juju run --all 'sh -c "%s"'""" % tar_cmd)

    @staticmethod
    def __retrieve_single_unit_tarball(unique, tuple_input):
        machine, alias_group = tuple_input
        unit_unique = uuid.uuid4()
        juju_cmd("scp %s:/tmp/juju-dump-%s.tar %s.tar"
                 % (machine, unique, unit_unique))
        if '/' not in machine:
            machine += '/baremetal'
        run_cmd("mkdir -p %s || true" % machine)
        try:
            run_cmd("tar -pxf %s.tar -C %s" % (unit_unique, machine))
            run_cmd("rm %s.tar" % unit_unique)
        except IOError:
            # If you are running crashdump as a machine is coming
            # up, or scp fails for some other reason, you won't
            # have a tarball to move. In that case, skip, and try
            # fetching the tarball for the next machine.
            print("Unable to retrieve tarball for %s. Skipping." % machine)
        for alias in alias_group:
            os.symlink('%s' % machine, '%s' % alias.replace('/', '_'))

    def retrieve_unit_tarballs(self):
        juju_status = yaml.load(open('juju_status.yaml', 'r'))
        aliases = service_unit_addresses(juju_status)
        if not aliases:
            # Running against an empty model.
            print("0 machines found. No tarballs to retrieve.")
            return
        pool = multiprocessing.Pool()
        tarball_collector = functools.partial(
            CrashCollector.__retrieve_single_unit_tarball, self.uniq)
        pool.map(tarball_collector, aliases.items())

    def collect(self):
        juju_check()
        juju_status()
        if 'debug_log.txt' not in self.exclude:
            juju_debuglog()
        self.run_addons()
        self.create_unit_tarballs()
        self.retrieve_unit_tarballs()
        tar_file = "juju-crashdump-%s.tar" % self.uniq
        run_cmd("tar -pcf %s * 2>/dev/null" % tar_file)
        run_cmd("xz --force %s" % tar_file)
        os.chdir(self.cwd)
        compressed_file = tar_file + '.xz'
        shutil.move(os.path.join(self.tempdir, compressed_file),
                    self.output_dir)
        self.cleanup()
        return compressed_file

    def cleanup(self):
        shutil.rmtree(self.tempdir)


def upload_file_to_bug(bugnum, file_):
    if not APPORT:
        # We guard against this by checking for APPORT when the script
        # first runs (see bottom of this file). Just in case we get
        # here without apport, inform the user and skip this routine.
        print(
            "Apport not available in this environment. "
            "Skipping upload file to bug."
        )
        return
    crashdb = crashdb = apport.crashdb.get_crashdb(None)
    if not crashdb.can_update(bugnum):
        print(dedent("""
            You are not the reporter or subscriber of this problem report,
            or the report is a duplicate or already closed.

            Please create a new report on https://bugs.launchpad.net/charms.
            """))
        return False

    is_reporter = crashdb.is_reporter(bugnum)

    report = apport.Report('Bug')
    apport.hookutils.attach_file(report, file_, overwrite=False)
    if len(report) != 0:
        print("Starting upload to lp:%s" % bugnum)
        crashdb.update(bugnum, report, 'apport information',
                       change_description=is_reporter,
                       attachment_comment='juju crashdump')


class ShowDescription(argparse.Action):
    """Helper for implementing --description using argparse"""
    def __init__(self, *args, **kwargs):
        super(ShowDescription, self).__init__(*args, **kwargs)

    def __call__(self, parser, *args, **kwargs):
        print(CrashCollector.__doc__)
        sys.exit(0)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--description', nargs=0, action=ShowDescription,
                        help='Output a short description of the plugin')
    parser.add_argument('-m', '--model', default=None,
                        help='Model to act on')
    parser.add_argument('-f', '--max-file-size',  default=MAX_FILE_SIZE,
                        help='The max file size (bytes) for included files')
    parser.add_argument('-b', '--bug', default=None,
                        help='Upload crashdump to the given launchpad bug #')
    parser.add_argument('extra_dir', nargs='*', default=[],
                        help='Extra directories to snapshot')
    parser.add_argument('-x', '--exclude', action='append',
                        help='Directories or files to exclude from capture.')
    parser.add_argument('-o', '--output-dir',
                        help="Store the completed crash dump in this dir.")
    parser.add_argument('-u', '--uniq',
                        help="Unique id for this crashdump. "
                        "We generate a uuid if this is not specified.")
    parser.add_argument('-s', '--small', action='store_true',
                        help="Make a 'small' crashdump, by skipping the "
                        "contents of /var/lib/juju.")
    parser.add_argument('-a', '--addon', action='append',
                        help='Enable the addon with the given name')
    parser.add_argument('--addons-file',  default=ADDONS_FILE_PATH,
                        help='Use this file for addon definitions')
    return parser.parse_args()


def main():
    opts = parse_args()
    if opts.bug and not APPORT:
        print("Apport not available in this environment. "
              "You must 'apt install' apport to use the 'bug' option. "
              "Aborting run.")
        return
    if not opts.small:
        DIRECTORIES.append('/var/lib/juju')
    collector = CrashCollector(
        model=opts.model,
        max_size=opts.max_file_size,
        extra_dirs=opts.extra_dir,
        output_dir=opts.output_dir,
        uniq=opts.uniq,
        addons=opts.addon,
        addons_file=opts.addons_file,
        exclude=opts.exclude
    )
    filename = collector.collect()
    if opts.bug:
        upload_file_to_bug(opts.bug, filename)


if __name__ == '__main__':
    main()
