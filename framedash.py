import can
import binascii
import curses
import json
import argparse
import threading
import csv
import time
from art import text2art
from curses import wrapper
from curses.textpad import Textbox
from pathlib import Path

bus = None
frameList = {}
paramList = {}
framePadScroll = 0
paramPadScroll = 0
captureActive = True
loggingActive = False
parameterDefs = []
channel = None
logger = None
logFile = None
playbackMode = False
vBusActive = False
paramRecordingFile = None
paramRecordingActive = False
csvWriter = None

def playbackDaemon(reader, stamp, delay):
    global bus, vBusActive, captureActive
    vBusActive = True
    for msg in can.MessageSync(messages=reader, timestamps=stamp, gap=delay):
        bus.send(msg)
    captureActive = False
    bus.shutdown()
    vBusActive = False
    return

parser = argparse.ArgumentParser(
    description="launch framedash utility with given can traffic source",
    epilog="Written by NPoole for Rising Tide Research Foundation 2026")
groupInterface = parser.add_argument_group("live interface mode")
groupPlayback = parser.add_argument_group("log playback mode")
groupInterface.add_argument("-i", "--interface", help="specify python-can interface (e.g. \"slcan\")")
groupInterface.add_argument("-c", "--channel", help="specify python-can channel")
groupInterface.add_argument("-b", "--bitrate", type=int, default=250000, help="specify python-can bitrate")
groupInterface.add_argument("-t", "--ttybaud", type=int, default=0, help="specify python-can interface baudrate for interfaces that require it")
groupPlayback.add_argument("-r", "--replay", default=None, help="log file to replay")
groupPlayback.add_argument("-d", "--delay", type=float, default=0, help="time in seconds between replay frames")
groupPlayback.add_argument("-s", "--stamp", action="store_false", help="ignore logfile timestamps on replay and use --delay value")
args = parser.parse_args()

if args.replay == None:
    try:
        channel = args.channel
        if args.ttybaud == 0:
            bus = can.interface.Bus(interface=args.interface, channel=args.channel, tty_baudrate=args.ttybaud, bitrate=args.bitrate)
        else:
            bus = can.interface.Bus(interface=args.interface, channel=args.channel, bitrate=args.bitrate)
    except can.exceptions.CanInterfaceNotImplementedError:
        print("CAN interface not recognized")
        raise SystemExit
    except can.exceptions.CanInitializationError:
        print("Bus failed to initialize")
        raise SystemExit    
    except ValueError:
        print("Invalid interface initialization arguments")
        raise SystemExit    
else:
    try:
        bus = can.ThreadSafeBus(interface="virtual", receive_own_messages=True)
        reader = can.LogReader(args.replay)
        #captureActive = False
        playback = threading.Thread(target=playbackDaemon, args=(reader, args.stamp, args.delay), daemon=True)
        playbackMode = True
        captureActive = False
    except ValueError:
        print("File Error")
        raise SystemExit

def convertToPGN(arbitration_id):
    priority = (arbitration_id>>26)&0b111
    reserved = (arbitration_id>>25)&0b1
    data_page = (arbitration_id>>24)&0b1
    pdu_format = (arbitration_id>>16)&0b11111111
    pdu_specific = (arbitration_id>>8)&0b11111111
    source_addr = (arbitration_id)&0b11111111
    global_pgn = 0 if pdu_format < 240 else pdu_specific
    pgn = (reserved<<17)|(data_page<<16)|(pdu_format<<8)|global_pgn
    return pgn

def paramListUpdate(msg, pad):
    global paramList, paramPadScroll, parameterDefs, paramRecordingActive
    parameterValue = None
    msgpgn = convertToPGN(msg.arbitration_id)
    for parameter in parameterDefs:
        if (parameter["id"] == msg.arbitration_id) or (parameter["pgn"] == msgpgn):
            bytematch = True
            for index, databyte in enumerate(parameter["pattern"]):
                if (databyte != None) and (databyte != msg.data[index]):
                    bytematch = False
            if bytematch == False: 
                break
            if parameter["msb"] < parameter["lsb"]:
                parameterValue = int.from_bytes(msg.data[parameter["msb"]:parameter["lsb"]+1], byteorder="big")
            else:
                parameterValue = int.from_bytes(msg.data[parameter["lsb"]:parameter["msb"]+1], byteorder="little")
            if parameter["radix"] == 2:
                parameterValue = bin(parameterValue)
            elif parameter["radix"] == 8:
                parameterValue = oct(parameterValue)
            elif parameter["radix"] == 16:
                parameterValue = hex(parameterValue)
            elif parameter["radix"] == 10:
                parameterValue = str(parameterValue)
            paramList.update({parameter["name"] : parameterValue})
            if paramRecordingActive:
                recordToFile({
                    "Timestamp": msg.timestamp,
                    "ParameterName": parameter["name"],
                    "Value": parameterValue
                })
    tableIdx = 0
    for name, value in paramList.items():
        pad.addstr(tableIdx, 0, str(tableIdx) + "\t" + name + "\t" + value)
        tableIdx += 1

def frameListUpdate(msg, pad):
    global frameList, framePadScroll
    curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLACK)
    CYAN_ON_BLACK = curses.color_pair(1)
    frameList.update({msg.arbitration_id : msg})
    tableIdx = 0
    for canID, canMsg in frameList.items():
        pgn = str(hex(convertToPGN(canID)))+"\t" if canMsg.is_extended_id else "[Std ID]"
        tabSpace = "\t" if canMsg.is_extended_id else "\t\t"
        if canID == msg.arbitration_id:
            pad.addstr(tableIdx, 0, str(tableIdx) + "\t" + str(hex(canID)) + tabSpace + pgn + "\t" + binascii.hexlify(canMsg.data).decode(), CYAN_ON_BLACK)
        else:
            pad.addstr(tableIdx, 0, str(tableIdx) + "\t" + str(hex(canID)) + tabSpace + pgn + "\t" + binascii.hexlify(canMsg.data).decode())
        tableIdx += 1
    return

def contextMenu(stdscr, menuColorPair):
    if playbackMode:
        stdscr.addstr(23, 0, ("Pause" if captureActive else "Resume") + " Playba[c]k ", menuColorPair)
    else:
        stdscr.addstr(23, 0, ("Pause" if captureActive else "Resume") + " [C]apture ", menuColorPair)
    stdscr.addstr(23, 20, ("Stop" if loggingActive else "Start") + " [L]ogging ", menuColorPair)
    stdscr.addstr(23, 40, "[N]ew Parameter", menuColorPair)
    stdscr.addstr(23, 60, "[D]elete Parameter", menuColorPair)
    stdscr.addstr(24, 0, "Edit Parame[t]er", menuColorPair)    
    stdscr.addstr(24, 20, "[S]ave Parameter Definitions", menuColorPair)
    stdscr.addstr(24, 50, "Load [P]arameter Definitions", menuColorPair)
    stdscr.addstr(25, 0, ("Stop" if paramRecordingActive else "Start") + " Parameter Rec[o]rding ", menuColorPair)
    stdscr.addstr(25, 30, "[E]xit", menuColorPair)
    return

def validateName(stdscr, input):
    global parameterDefs
    if len(input) > 20:
        stdscr.addstr(28, 0, "(Name should be shorter than 20 characters)")
        return False
    else:
        for definition in parameterDefs:
            if input == definition["name"]:
                stdscr.addstr(28, 0, "(Parameter definitions must be unique)")
                return False
        return True

def validateID(stdscr, input):
    if input == "":
        return True
    try:
        value = int(input, 16)
        if value <= 0x1FFFFFFF:
            return True
        else:
            stdscr.addstr(28, 0, "(Arbitration ID must be less than 0x1FFFFFFF)")
            return False
    except ValueError:
        stdscr.addstr(28, 0, "(Arbitration ID must be in valid hexadecimal format)")
        return False

def validatePGN(stdscr, input):
    if input == "":
        stdscr.addstr(28, 0, "(Parameter must reference a CAN ID or PGN)")
        return False
    try:
        value = int(input, 16)
        if value <= 0x1FFFF:
            return True
        else:
            stdscr.addstr(28, 0, "(PGN must be less than 0x1FFFF)")
            return False
    except ValueError:
        stdscr.addstr(28, 0, "(PGN must be in valid hexadecimal format)")
        return False

def validateByte(stdscr, input):
    if input == "":
        return True
    try:
        value = int(input, 16)
        if value <= 0xFF:
            return True
        else:
            stdscr.addstr(28, 0, "(Please specify a single byte)")
            return False
    except ValueError:
        stdscr.addstr(28, 0, "(Byte match must be in valid hexadecimal format)")
        return False

def validatePos(stdscr, input):
    if input == "":
        stdscr.addstr(28, 0, "(Byte position must be 0-7)")
        return False    
    try:
        value = int(input, 10)
        if value <= 7:
            return True
        else:
            stdscr.addstr(28, 0, "(Byte position must be 0-7)")
            return False
    except ValueError:
        stdscr.addstr(28, 0, "(Byte position must be 0-7)")
        return False    

def validateRadix(stdscr, input):
    if input.strip() in ("2", "8", "10", "16"):
        return True
    else:
        stdscr.addstr(28, 0, "(Radix must be 2, 8, 10 or 16)")
        return False

def validateParamIndex(stdscr, input):
    global paramList
    if input == "":
        stdscr.addstr(28, 0, "(Table position not found)")
        return False    
    try:
        value = int(input, 10)
        if value < len(paramList):
            return True
        else:
            stdscr.addstr(28, 0, "(Table position not found)")
            return False
    except ValueError:
        stdscr.addstr(28, 0, "(Table position must be a number)")
        return False        

def validateTrue(stdscr, input):
    return True

def validateYN(stdscr, input):
    if input.strip() in ("y", "n"):
        return True
    else:
        stdscr.addstr(28, 0, "(Response must be y or n)")
        return False    

def promptUser(stdscr, promptWin, promptBox, prompt, validator, initial):
    validated = False
    while(validated == False):
        stdscr.addstr(26, 0, "                                                                                              ")
        stdscr.refresh()    
        stdscr.addstr(26, 0, prompt)
        stdscr.refresh()
        if initial != None:
            promptWin.addstr(0,0,initial)
        promptBox.edit()
        response = promptBox.gather()
        promptWin.clear()
        if validator(stdscr, response):
            validated = True
    if response == "":
        response = None  
    stdscr.addstr(28, 0, "                                                                                              ")
    return response

def createParameter(stdscr, promptWin, editParam):
    global parameterDefs
    promptBox = Textbox(promptWin)
    paramName = promptUser(stdscr, promptWin, promptBox, "Name your new parameter:", validateName, editParam['name'] if editParam != None else None)
    paramID = promptUser(stdscr, promptWin, promptBox, "Arbitration ID to match (Hex format, leave blank to match on PGN):", validateID, f"{editParam['id']:X}" if editParam != None else None)
    paramPGN = None
    if paramID == None: 
        paramPGN = int(promptUser(stdscr, promptWin, promptBox, "PGN to match (Hex format):", validatePGN, f"{editParam['pgn']:X}" if editParam != None else None), 16)
    else:
        paramID = int(paramID, 16)
    paramPattern = []
    paramPattern.insert(0, promptUser(stdscr, promptWin, promptBox, "Match for data byte 0 (Hex format, leave blank to match any):", validateByte, f"{editParam['pattern'][0]:X}" if (editParam != None) and (editParam['pattern'][0] != None) else None))
    paramPattern.insert(1, promptUser(stdscr, promptWin, promptBox, "Match for data byte 1 (Hex format, leave blank to match any):", validateByte, f"{editParam['pattern'][1]:X}" if (editParam != None) and (editParam['pattern'][1] != None) else None))
    paramPattern.insert(2, promptUser(stdscr, promptWin, promptBox, "Match for data byte 2 (Hex format, leave blank to match any):", validateByte, f"{editParam['pattern'][2]:X}" if (editParam != None) and (editParam['pattern'][2] != None) else None))
    paramPattern.insert(3, promptUser(stdscr, promptWin, promptBox, "Match for data byte 3 (Hex format, leave blank to match any):", validateByte, f"{editParam['pattern'][3]:X}" if (editParam != None) and (editParam['pattern'][3] != None) else None))
    paramPattern.insert(4, promptUser(stdscr, promptWin, promptBox, "Match for data byte 4 (Hex format, leave blank to match any):", validateByte, f"{editParam['pattern'][4]:X}" if (editParam != None) and (editParam['pattern'][4] != None) else None))
    paramPattern.insert(5, promptUser(stdscr, promptWin, promptBox, "Match for data byte 5 (Hex format, leave blank to match any):", validateByte, f"{editParam['pattern'][5]:X}" if (editParam != None) and (editParam['pattern'][5] != None) else None))
    paramPattern.insert(6, promptUser(stdscr, promptWin, promptBox, "Match for data byte 6 (Hex format, leave blank to match any):", validateByte, f"{editParam['pattern'][6]:X}" if (editParam != None) and (editParam['pattern'][6] != None) else None))
    paramPattern.insert(7, promptUser(stdscr, promptWin, promptBox, "Match for data byte 7 (Hex format, leave blank to match any):", validateByte, f"{editParam['pattern'][7]:X}" if (editParam != None) and (editParam['pattern'][7] != None) else None))
    for index, paramDB in enumerate(paramPattern):
        if paramDB != None:
            paramPattern[index] = int(paramDB, 16)
    paramDataBytesStart = int(promptUser(stdscr, promptWin, promptBox, "Beginning of bytes to be interpreted? (MSB = 0, Inclusive)", validatePos, str(editParam['msb']) if editParam != None else None), 10)
    paramDataBytesEnd = int(promptUser(stdscr, promptWin, promptBox, "End of bytes to be interpreted? (MSB = 0, Inclusive)", validatePos, str(editParam['lsb']) if editParam != None else None), 10)
    paramRadix = int(promptUser(stdscr, promptWin, promptBox, "Convert data fields to new radix? (2,8,10,16)", validateRadix, str(editParam['radix']) if editParam != None else None), 10)
    parameterDefs.append({
        "name":paramName,
        "id":paramID,
        "pgn":paramPGN,
        "pattern":paramPattern,
        "msb":paramDataBytesStart,
        "lsb":paramDataBytesEnd,
        "radix":paramRadix
    })
    stdscr.addstr(26, 0, "                                                                                              ")
    stdscr.addstr(28, 0, "                                                                                              ")
    promptWin.clear()
    return

def deleteParameter(stdscr, promptWin, paramPad):
    global parameterDefs, paramList
    if len(paramList) == 0:
        return
    promptBox = Textbox(promptWin)
    deleteIndex = promptUser(stdscr, promptWin, promptBox, "Table index of parameter to delete:", validateParamIndex, None)
    nameToDelete = list(paramList.keys())[int(deleteIndex, 10)]
    paramList.pop(nameToDelete)
    for index, definition in enumerate(parameterDefs):
        if definition["name"] == nameToDelete:
            parameterDefs.pop(index)
    stdscr.addstr(26, 0, "                                                                                              ")
    stdscr.addstr(28, 0, "                                                                                              ")
    promptWin.clear()  
    paramPad.clear()          
    return

def editParameter(stdscr, promptWin, paramPad):
    global parameterDefs, paramList
    if len(paramList) == 0:
        return    
    promptBox = Textbox(promptWin)
    deleteIndex = promptUser(stdscr, promptWin, promptBox, "Table index of parameter to edit:", validateParamIndex, None)
    nameToDelete = list(paramList.keys())[int(deleteIndex, 10)]
    paramList.pop(nameToDelete)
    for index, definition in enumerate(parameterDefs):
        if definition["name"] == nameToDelete:
            parameterToEdit = definition
            parameterDefs.pop(index)
    stdscr.addstr(26, 0, "                                                                                              ")
    stdscr.addstr(28, 0, "                                                                                              ")
    promptWin.clear()  
    paramPad.clear()         
    createParameter(stdscr, promptWin, parameterToEdit)
    return    

def saveParameterDefs(stdscr, promptWin):
    global parameterDefs
    if len(parameterDefs) == 0:
        return
    promptBox = Textbox(promptWin)
    while True:
        filepath = promptUser(stdscr, promptWin, promptBox, "Filename to save parameter definitions:", validateTrue, None)
        stdscr.addstr(28, 0, "                                                                                              ")
        try:
            with open(filepath.strip() + ".json", "x") as f:
                json.dump(parameterDefs, f)
                f.close()
                stdscr.addstr(26, 0, "                                                                                              ")
                stdscr.addstr(28, 0, "                                                                                              ")
                promptWin.clear()                
                return
        except FileNotFoundError:
            stdscr.addstr(28, 0, "(Filename is invalid)")
        except PermissionError:
            stdscr.addstr(28, 0, "(You do not have permission to access this file)")
        except FileExistsError:
            stdscr.addstr(28, 0, "(File already exists)")

def loadParameterDefs(stdscr, promptWin, paramPad):
    global parameterDefs, paramList
    promptBox = Textbox(promptWin)
    if len(parameterDefs) > 0:
        saveFirst = promptUser(stdscr, promptWin, promptBox, "Loading will overwrite the current list. Save first? (y/n)", validateYN, None)
        if saveFirst.strip() == "y":
            stdscr.addstr(26, 0, "                                                                                              ")
            stdscr.addstr(28, 0, "                                                                                              ")
            promptWin.clear()
            saveParameterDefs(stdscr, promptWin)
    while True:
        filepath = promptUser(stdscr, promptWin, promptBox, "Filename to load:", validateTrue, None)
        stdscr.addstr(28, 0, "                                                                                              ")
        try:
            with open(filepath.strip() + ".json", "r") as f:
                parameterDefs = json.load(f)
                f.close()
                paramList.clear()
                paramPad.clear()
                stdscr.addstr(26, 0, "                                                                                              ")
                stdscr.addstr(28, 0, "                                                                                              ")
                promptWin.clear()                
                return
        except FileNotFoundError:
            stdscr.addstr(28, 0, "(File not found)")
        except PermissionError:
            stdscr.addstr(28, 0, "(You do not have permission to access this file)")

def startLogging(stdscr, promptWin):
    global channel, logger, logFile
    promptBox = Textbox(promptWin)
    while True:
        filepath = promptUser(stdscr, promptWin, promptBox, "Filename to save logfile:", validateTrue, None)
        stdscr.addstr(28, 0, "                                                                                              ")
        try:
            logFile = open(filepath.strip() + ".log", "x")
            stdscr.addstr(26, 0, "                                                                                              ")
            stdscr.addstr(28, 0, "                                                                                              ")
            promptWin.clear()                
            try: 
                logger = can.CanutilsLogWriter(logFile, channel=channel, append=False)
                return
            except ValueError:
                stdscr.addstr(28, 0, "(File Error)")
        except FileNotFoundError:
            stdscr.addstr(28, 0, "(Filename is invalid)")
        except PermissionError:
            stdscr.addstr(28, 0, "(You do not have permission to access this file)")
        except FileExistsError:
            stdscr.addstr(28, 0, "(File already exists)")

def startParamRecording(stdscr, promptWin):
    global paramRecordingFile, paramRecordingActive, csvWriter
    if len(paramList) == 0:
        return False   
    try:
        paramRecordingFile = open("parameters"+str(int(time.time()))+".csv", "w", newline='')
        paramRecordingActive = True
        columns = ['Timestamp','ParameterName','Value']
        csvWriter = csv.DictWriter(paramRecordingFile, fieldnames=columns, extrasaction='ignore')
        csvWriter.writeheader()
        return True
    except PermissionError:
        print("log outfile permission error")
        return False
    except OSError:
        print("Disk Error writing log file")
        return False

def endParamRecording(stdscr, promptWin):
    global paramRecordingFile, paramRecordingActive
    try:
        paramRecordingFile.close()
    except:
        pass
    paramRecordingActive = False
    return True

def recordToFile(row):
    global paramRecordingFile, csvWriter
    if paramRecordingFile == None:
        return
    csvWriter.writerow(row)    
    return

def exitConfirm(stdscr, promptWin):
    promptBox = Textbox(promptWin)
    confirmed = promptUser(stdscr, promptWin, promptBox, "Are you sure you want to exit? (y/n)", validateYN, None)
    if confirmed.strip() == "y":
        stdscr.addstr(26, 0, "                                                                                              ")
        stdscr.addstr(28, 0, "                                                                                              ")
        promptWin.clear()
        try:
            if paramRecordingActive:
                endParamRecording(stdscr, promptWin)
            if loggingActive:
                logFile.close()    
            bus.shutdown()
        except:
            pass
        raise SystemExit
    else:
        stdscr.addstr(26, 0, "                                                                                              ")
        stdscr.addstr(28, 0, "                                                                                              ")
        promptWin.clear()
        return         

def main(stdscr):
    global framePadScroll, paramPadScroll, frameList, parameterList, captureActive, loggingActive, logger, paramRecordingActive
    stdscr.keypad(True)
    stdscr.nodelay(True)
    curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_WHITE)
    BLACK_ON_WHITE = curses.color_pair(2)
    curses.init_pair(3, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
    MAGENTA_ON_BLACK = curses.color_pair(3)
    curses.init_pair(4, curses.COLOR_WHITE, curses.COLOR_CYAN)
    WHITE_ON_CYAN = curses.color_pair(4)
    stdscr.clear()
    stdscr.addstr(text2art("FrameDash", font='tarty4'))
    stdscr.addstr(5, 0,"INCOMING FRAME TABLE", BLACK_ON_WHITE)
    stdscr.addstr(14, 0,"LIVE PARAMETER TABLE", BLACK_ON_WHITE)
    stdscr.addstr(12, 0,"(Scroll with PgUp/PgDn)", MAGENTA_ON_BLACK)
    stdscr.addstr(21, 0,"(Scroll with Home/End)", MAGENTA_ON_BLACK)
    contextMenu(stdscr, WHITE_ON_CYAN)  
    framePad = curses.newpad(1000,100)
    paramPad = curses.newpad(1000,100)
    promptWin = curses.newwin(1,100,27,0)
    while True:
        try:
            try:
                key = stdscr.getkey()
            except:
                key = None
            if key == "KEY_NPAGE":
                if framePadScroll < len(frameList): framePadScroll += 1 
            elif key == "KEY_PPAGE":
                if framePadScroll >= 0: framePadScroll -= 1
            elif key == "KEY_END":
                if paramPadScroll < len(parameterList): paramPadScroll += 1 
            elif key == "KEY_HOME":
                if paramPadScroll >= 0: paramPadScroll -= 1
            elif key == 'c':
                if captureActive:
                    captureActive = False
                    contextMenu(stdscr, WHITE_ON_CYAN)
                else:
                    captureActive = True
                    if playbackMode and not vBusActive:
                        playback.start()
                    contextMenu(stdscr, WHITE_ON_CYAN)
            elif key == 'l':
                if loggingActive:
                    logFile.close()
                    loggingActive = False
                    contextMenu(stdscr, WHITE_ON_CYAN)
                else:
                    startLogging(stdscr, promptWin)
                    loggingActive = True
                    contextMenu(stdscr, WHITE_ON_CYAN)
            elif key == 'o':
                if paramRecordingActive:
                    if endParamRecording(stdscr, promptWin):
                        paramRecordingActive = False
                    contextMenu(stdscr, WHITE_ON_CYAN)
                else:
                    if startParamRecording(stdscr, promptWin):
                        paramRecordingActive = True
                    contextMenu(stdscr, WHITE_ON_CYAN)                    
            elif key == 'e':
                exitConfirm(stdscr, promptWin)         
            elif key == 'n':
                createParameter(stdscr, promptWin, None)
            elif key == 'd':
                deleteParameter(stdscr, promptWin, paramPad)
            elif key == 't':
                editParameter(stdscr, promptWin, paramPad)    
            elif key == 's':
                saveParameterDefs(stdscr, promptWin)
            elif key == 'p':
                loadParameterDefs(stdscr, promptWin, paramPad)
            msg = bus.recv(1) if captureActive else None
            if msg != None:
                frameListUpdate(msg, framePad)
                paramListUpdate(msg, paramPad)
                if loggingActive:
                    logger(msg)
            framePad.refresh(framePadScroll,0,6,0,11,100)
            paramPad.refresh(paramPadScroll,0,15,0,20,100)
            promptWin.refresh()
            stdscr.refresh()
        except Exception as e:
            pass
            print(e)

wrapper(main)