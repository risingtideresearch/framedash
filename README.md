# framedash
```

▒█▀▀▀ █▀▀█ █▀▀█ █▀▄▀█ █▀▀ ▒█▀▀▄ █▀▀█ █▀▀ █░░█
▒█▀▀▀ █▄▄▀ █▄▄█ █░▀░█ █▀▀ ▒█░▒█ █▄▄█ ▀▀█ █▀▀█
▒█░░░ ▀░▀▀ ▀░░▀ ▀░░░▀ ▀▀▀ ▒█▄▄▀ ▀░░▀ ▀▀▀ ▀░░▀

usage: framedash.py [-h] [-i INTERFACE] [-c CHANNEL] [-b BITRATE] [-t TTYBAUD] [-r REPLAY] [-d DELAY] [-s]

launch framedash utility with given can traffic source

optional arguments:
  -h, --help            show this help message and exit

live interface mode:
  -i INTERFACE, --interface INTERFACE
                        specify python-can interface (e.g. "slcan")
  -c CHANNEL, --channel CHANNEL
                        specify python-can channel
  -b BITRATE, --bitrate BITRATE
                        specify python-can bitrate
  -t TTYBAUD, --ttybaud TTYBAUD
                        specify python-can interface baudrate for interfaces that require it

log playback mode:
  -r REPLAY, --replay REPLAY
                        log file to replay
  -d DELAY, --delay DELAY
                        time in seconds between replay frames
  -s, --stamp           ignore logfile timestamps on replay and use --delay value

```

## What is framedash?

```
▒█▀▀▀ █▀▀█ █▀▀█ █▀▄▀█ █▀▀ ▒█▀▀▄ █▀▀█ █▀▀ █░░█
▒█▀▀▀ █▄▄▀ █▄▄█ █░▀░█ █▀▀ ▒█░▒█ █▄▄█ ▀▀█ █▀▀█
▒█░░░ ▀░▀▀ ▀░░▀ ▀░░░▀ ▀▀▀ ▒█▄▄▀ ▀░░▀ ▀▀▀ ▀░░▀

INCOMING FRAME TABLE
0       0x1cefff24      0xef00          6699dbed4a070000
1       0x305           [Std ID]        0000000000000000
2       0x307           [Std ID]        1234567856494300
3       0x1cef24e1      0xef00          669901002720ffff
4       0x19f21424      0x1f214         00851400008f70d3
5       0x19f21224      0x1f212         01ffffffffffffff
(Scroll with PgUp/PgDn)

LIVE PARAMETER TABLE
0       Test Parameter  36720





(Scroll with Home/End)

Resume [C]apture    Start [L]ogging     [N]ew Parameter     [D]elete Parameter
[S]ave Parameter Definitions  Load [P]arameter Definitions  [E]xit
```

framedash provides a Terminal User Interface (TUI) for monitoring and logging CAN traffic while extracting specific data based on pattern matching. framedash is intended to aid in the exploration of proprietary higher-layer protocols on the CAN bus. 

## Launching framedash

framedash can be launched in two different modes: live mode or playback mode. In live mode, framedash connects to a python-can interface to receive live traffic. In playback mode, framedash reads from a pre-recorded log file. 

### Launching in Live Mode

framedash takes up to 4 arguments to specify the CAN message source. These arguments are derived from the [python-can Bus API](https://python-can.readthedocs.io/en/stable/bus.html#can.Bus).

```
  -i INTERFACE, --interface INTERFACE
                        specify python-can interface (e.g. "slcan")
  -c CHANNEL, --channel CHANNEL
                        specify python-can channel
  -b BITRATE, --bitrate BITRATE
                        specify python-can bitrate
  -t TTYBAUD, --ttybaud TTYBAUD
                        specify python-can interface baudrate for interfaces that require it
```

For example: `framedash.py -i slcan -c COM6 -t 500000`

### Launching in Playback Mode

framedash takes up to 3 arguments to specify the logfile playback behavior. These arguments are derived from the [python-can MessageSync method](https://python-can.readthedocs.io/en/stable/file_io.html#can.MessageSync). **When framedash is launched in Playback Mode, playback will be paused.** This allows for the user to load a parameter file before starting playback.

```
  -r REPLAY, --replay REPLAY
                        log file to replay
  -d DELAY, --delay DELAY
                        time in seconds between replay frames
  -s, --stamp           ignore logfile timestamps on replay and use --delay value
```

For example: `framedash.py -r demolog.log`

## Using framedash

### Incoming Frame Table

The Incoming Frame Table shows the the live CAN traffic in overwrite mode, i.e. stale frames are overwritten by new frames with the same ID. Table entries are highlighted in blue whenever they are written in order to spotlight these overwrites. The Incoming Frame Table can sometimes reveal patterns in bus traffic and it acts as a useful reference while defining new parameters. Capture/Playback can be paused and resumed by pressing the `c` key. The table can be scrolled up and down using the `PgUp` and `PgDn` keys.

### Live Parameter Table

The Live Parameter Table shows the current value of all parameters extracted from the CAN traffic. Each parameter is updated whenever a new CAN frame is received which matches its definition. The table can be scrolled up and down using the `Home` and `End` keys.

### Defining a New Parameter

A key feature of framedash is the ability to match incoming CAN frames to a template called a Parameter Definition and extract the value of a byte or several bytes. Frames can be matched based on either their Arbitration ID or PGN in combination with any number of byte values in the data field. The Parameter Definition also specifies a byte position or range of byte positions in the data field to extract and display in the Live Parameter Table. Pressing `n` opens the New Parameter dialog. 

#### Parameter Name
Names can be any string up to 20 characters, including spaces. This is the text that is displayed next to the extracted value in the Live Parameter Table.

#### Arbitration ID
Arbitration ID should be entered in hexadecimal format without the "0x" prefix. 11- and 29-bit IDs are both accepted. Leaving this field blank will prompt the user to match on a PGN instead. 

#### PGN
PGN should be entered in hexadecimal format without the "0x" prefix. A Parameter Definition **must** contain either an Arbitration ID or PGN. 

#### Data Byte Matches
The value for each byte position to be matched should be entered in hexadecimal format without the "0x" prefix. The user is prompted for each of 8 values starting from left-most byte 0. Leaving a position blank will match *any* value in that position.

#### Bytes to Be Interpreted
Byte positions are zero-indexed left-to-right, ordered, and inclusive. Multiple bytes selected together are interpreted as a single value with the number's Endianness determined by the order of the "beginning" and "end" positions. For example, in the data frame `[66 99 23 53 5A CB FF FF]` the value returned by `beginning=2 end=4` would be `0x23535A`, whereas the value returned by `beginning=4 end=2` would be `0x5A5323`.

#### Convert to New Radix
The extracted byte value can be displayed in the Live Parameter Table in radix 2, 8, 10, or 16 for ease of interpretation.

### Deleting a Parameter
If a Parameter Definition is no longer needed, it can be deleted by pressing the 'd' key, followed by the table index of the parameter to delete. This will remove the entry from the Live Parameter Table as well as the Parameter Definition itself. 

### Saving and Loading Parameter Files
It may be desirable to save all of the Parameter Definitions from one session and open them in another. To do this, simply press the `s` key and enter a filename for the Parameter Definition JSON file. To load a file, press the `p` key. Loading a Parameter Definitions file will overwrite any Parameter Definitions already in the table. If framedash detects that the table is not empty, it will ask whether the user would like to save the existing Parameter Defintions before loading new ones. 

### Writing a Log File
Log files are recorded in can-utils `.log` format. To start a log recording, press the `l` key and enter a filename for the log. All incoming frames will be recorded to this log file until the `l` key is pressed again. These log files can be replayed in framedash Playback Mode. 

### Playing a Log File

