# juju-crashdump

Script to assist in gathering logs and other debugging info from a Juju model

## Installation

The best way to install this plugin is via the snap:

```
sudo snap install --classic juju-crashdump
```

However, you can also install using pip:

```
sudo pip install git+https://github.com/juju/juju-crashdump.git
```


## Usage

```
juju crashdump [-h] [-d] [-m MODEL] [-f MAX_FILE_SIZE] [-b BUG]
               [-o OUTPUT_DIR] [-u UNIQ] [-s] [-a ADDON]
               [--addons-file ADDONS_FILE]
               [extra_dir [extra_dir ...]]
```

<dl>
<dt>extra_dir</dt>
<dd>Extra directories to snapshot</dd>
<dt>-h, --help</dt>
<dd>show this help message and exit</dd>
<dt>-d, --description</dt>
<dd>Output a short description of the plugin</dd>
<dt>-m MODEL, --model MODEL</dt>
<dd>Model to act on</dd>
<dt>-f MAX_FILE_SIZE, --max-file-size MAX_FILE_SIZE</dt>
<dd>The max file size (bytes) for included files</dd>
<dt>-b BUG, --bug BUG</dt>
<dd>Upload crashdump to the given launchpad bug #</dd>
<dt>-o OUTPUT_DIR, --output-dir OUTPUT_DIR</dt>
<dd>Store the completed crash dump in this dir.</dd>
<dt>-u UNIQ, --uniq UNIQ</dt>
<dd>Unique id for this crashdump. We generate a uuid if this is not specified.</dd>
<dt>-s, --small</dt>
<dd>Make a 'small' crashdump, by skipping the contents of /var/lib/juju.</dd>
<dt>-a ADDON, --addon ADDON</dt>
<dd>Enable the addon with the given name</dd>
<dt>--addons-file ADDONS_FILE</dt>
<dd>Use this file for addon definitions</dd>
<dt>--as-root</dt>
<dd>Collect logs as root, may contain passwords etc. Addons with local commands will only run if this flag is enabled.</dd>
</dl>

### Addons

Addons can be used to collect information that is not already present in files on the nodes.
The following addons can be chosen from:
 - crm-status
 - listening (shows netstat)
 - psaux
 - juju-show-unit
 - juju-show-status-log
 - juju-show-machine
 - [ps-mem](https://github.com/fginther/ps_mem.git)
 - [sosreport](https://github.com/sosreport/sos.git)
 - config (shows juju-config)
 - engine-report (shows juju-introspection)

Additional addons can be loaded using `--addons-file`. Addons files must take the format of:
```yaml
addon-name:
 # command to run locally (on the machine running juju crashdump),
 # all created files will be pushed to {location} on all units.
 local: echo "example" > example.txt
 # command to run on every unit, all files created in {output} will be saved in the crashdump.
 remote: mv {location}/example.txt {output}/example.txt
 # local command to run for each {unit} or each {machine}. Std output will be saved.
 local-per-unit: echo "example including {unit}"
```
The commands can appear in any order, any command can be left out, but every command can only be used once.
