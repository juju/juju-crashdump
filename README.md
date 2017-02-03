# juju-crashdump

Script to assist in gathering logs and other debugging info from a Juju model

## Usage

```
juju crashdump [-h] [-d] [-m MODEL] [-f MAX_FILE_SIZE] [-b BUG]
               [-o OUTPUT_DIR] [-u UNIQ]
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
</dl>
