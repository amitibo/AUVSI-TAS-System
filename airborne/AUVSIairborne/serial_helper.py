import serial.tools.list_ports as serports

def findSerialDevice(vid, pid):
    # Detect serial port of a specific device
    ports = list(serports.comports())

    str1 = ('VID:PID=%04X:%04X' % (vid, pid)).lower()
    str2 = ('VID_%04X&PID_%04X' % (vid, pid)).lower()

    for p in ports:
        if str1 in p[2].lower() or str2 in p[2].lower():
            return p[0]

    return None
