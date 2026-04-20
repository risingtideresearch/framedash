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

The Live Parameter Table shows the current value of all Parameters extracted from the CAN traffic. Each Parameter is updated whenever a new CAN frame is received which matches its definition. The table can be scrolled up and down using the `Home` and `End` keys.

### Defining a New Parameter

### Deleting a Parameter

### Saving and Loading Parameter Files

### Writing a Log File
