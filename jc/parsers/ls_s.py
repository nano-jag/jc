"""jc - JSON CLI output utility `ls` and `vdir` command output streaming parser

This streaming parser requires the `-l` option to be used on `ls`. If there are newline characters in the filename, then make sure to use the `-b` option on `ls`.

The `jc` `-q` option can be used to ignore parsing errors. (e.g. filenames with newline characters, but `-b` was not used)

The `epoch` calculated timestamp field is naive (i.e. based on the local time of the system the parser is run on)

The `epoch_utc` calculated timestamp field is timezone-aware and is only available if the timezone field is UTC.

Usage (cli):

    $ ls | jc --ls-s

Usage (module):

    import jc.parsers.ls_s
    result = jc.parsers.ls_s.parse(ls_command_output)    # result is an iterable object
    for item in result:
        # do something

Schema:

    {
      "filename":       string,
      "flags":          string,
      "links":          integer,
      "parent":         string,
      "owner":          string,
      "group":          string,
      "size":           integer,
      "date":           string,
      "epoch":          integer,     # naive timestamp if date field exists and can be converted
      "epoch_utc":      integer,     # timezone aware timestamp if date field is in UTC and can be converted
      "_meta":                       # This object only exists if using -q or quiet=True
        {
          "success":    booean,      # true if successfully parsed, false if error
          "error_msg":  string,      # exists if "success" is false
          "line":       string       # exists if "success" is false
        }
    }

Examples:

    $ ls -l /usr/bin | jc --ls-s
    {"filename":"2to3-","flags":"-rwxr-xr-x","links":4,"owner":"root","group":"wheel","size":925,"date":"Feb 22 2019"}
    {"filename":"2to3-2.7","link_to":"../../System/Library/Frameworks/Python.framework/Versions/2.7/bin/2to3-2.7","flags":"lrwxr-xr-x","links":1,"owner":"root","group":"wheel","size":74,"date":"May 4 2019"}
    {"filename":"AssetCacheLocatorUtil","flags":"-rwxr-xr-x","links":1,"owner":"root","group":"wheel","size":55152,"date":"May 3 2019"}
    ...

    $ ls -l /usr/bin | jc --ls-s -r
    {"filename":"2to3-","flags":"-rwxr-xr-x","links":"4","owner":"root","group":"wheel","size":"925","date":"Feb 22 2019"}
    {"filename":"2to3-2.7","link_to":"../../System/Library/Frameworks/Python.framework/Versions/2.7/bin/2to3-2.7","flags":"lrwxr-xr-x","links":"1","owner":"root","group":"wheel","size":"74","date":"May 4 2019"}
    {"filename":"AssetCacheLocatorUtil","flags":"-rwxr-xr-x","links":"1","owner":"root","group":"wheel","size":"55152","date":"May 3 2019"}
    ...
"""
import re
import jc.utils
from jc.utils import stream_success, stream_error
from jc.exceptions import ParseError


class info():
    """Provides parser metadata (version, author, etc.)"""
    version = '0.5'
    description = '`ls` command streaming parser'
    author = 'Kelly Brazil'
    author_email = 'kellyjonbrazil@gmail.com'

    # compatible options: linux, darwin, cygwin, win32, aix, freebsd
    compatible = ['linux', 'darwin', 'cygwin', 'aix', 'freebsd']
    streaming = True


__version__ = info.version


def _process(proc_data):
    """
    Final processing to conform to the schema.

    Parameters:

        proc_data:   (Dictionary) raw structured data to process

    Returns:

        Dictionary. Structured data to conform to the schema.
    """
    int_list = ['links', 'size']
    for key in proc_data:
        if key in int_list:
            proc_data[key] = jc.utils.convert_to_int(proc_data[key])

    if 'date' in proc_data:
        # to speed up processing only try to convert the date if it's not the default format
        if not re.match(r'[a-zA-Z]{3}\s{1,2}\d{1,2}\s{1,2}[0-9:]{4,5}', proc_data['date']):
            ts = jc.utils.timestamp(proc_data['date'])
            proc_data['epoch'] = ts.naive
            proc_data['epoch_utc'] = ts.utc

    return proc_data


def parse(data, raw=False, quiet=False):
    """
    Main text parsing generator function. Produces an iterable object.

    Parameters:

        data:        (string)  line-based text data to parse
        raw:         (boolean) output preprocessed JSON if True
        quiet:       (boolean) suppress warning messages and ignore parsing errors if True

    Yields:

        Dictionary. Raw or processed structured data.
    """
    if not quiet:
        jc.utils.compatibility(__name__, info.compatible)

    parent = ''

    for line in data:
        try:

            # skip line if it starts with 'total 1234'
            if re.match(r'total [0-9]+', line):
                continue

            # skip blank lines
            if line.strip() == '':
                continue

            # Look for parent line if glob or -R is used
            if not re.match(r'[-dclpsbDCMnP?]([-r][-w][-xsS]){2}([-r][-w][-xtT])[+]?', line) \
               and line.strip().endswith(':'):
                parent = line.strip()[:-1]
                continue

            if not re.match(r'[-dclpsbDCMnP?]([-r][-w][-xsS]){2}([-r][-w][-xtT])[+]?', line):
                raise ParseError(f'Unable to parse line: {line.strip()[:40]}')

            parsed_line = line.strip().split(maxsplit=8)
            output_line = {}

            # split filenames and links
            if len(parsed_line) == 9:
                filename_field = parsed_line[8].split(' -> ')
            else:
                # in case of filenames starting with a newline character
                filename_field = ['']

            # create output object
            output_line['filename'] = filename_field[0]

            if len(filename_field) > 1:
                output_line['link_to'] = filename_field[1]

            if parent:
                output_line['parent'] = parent

            output_line['flags'] = parsed_line[0]
            output_line['links'] = parsed_line[1]
            output_line['owner'] = parsed_line[2]
            output_line['group'] = parsed_line[3]
            output_line['size'] = parsed_line[4]
            output_line['date'] = ' '.join(parsed_line[5:8])

            yield stream_success(output_line, quiet) if raw else stream_success(_process(output_line), quiet)
            
        except Exception as e:
            yield stream_error(e, quiet, line)
