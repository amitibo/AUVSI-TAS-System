import serial
from serial_helper import findSerialDevice
import sys
from time import sleep

class ZoomController:
    DEFAULT_BAUD = 115200
    DEFAULT_VID = 0x067B
    DEFAULT_PID = 0x2303

    def __init__(self):
        self._port = None
        self._baud = None
        self._detectPort()
        self._ser = serial.Serial(self._port, self._baud)

    def zoom(self, zoomIn):
        if zoomIn:
            cmd = 'z+'
        else:
            cmd = 'z-'

        cmd += '\r\n'

        for i in range(30):
            if i > 0:
                sleep(0.1)

            self._ser.write(cmd)

    def _detectPort(self):
        # find Arduino com port
        #self._port = findSerialDevice(self.DEFAULT_VID, self.DEFAULT_PID)
        self._port = '/dev/ttyUSB1'

        if self._port is None:
            raise Exception('Zoom controller %04x:%04x not detected' % (self.DEFAULT_VID, self.DEFAULT_PID))

        self._baud = self.DEFAULT_BAUD

if __name__ == '__main__':
    z = ZoomController()
    zoomIn = True

    if len(sys.argv) > 1:
        zoomIn = (sys.argv[1] != 'out')

    z.zoom(zoomIn)
