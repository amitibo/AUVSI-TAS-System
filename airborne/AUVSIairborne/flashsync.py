import multiprocessing as mp
import serial
from serial_helper import findSerialDevice
import datetime

class FlashSync:
    DEFAULT_BAUD = 9600
    DEFAULT_VID = 0x1A86
    DEFAULT_PID = 0x7523

    def __init__(self):
        self._port = None
        self._baud = None
        self._timeQueue = mp.Queue()
        self._syncQueue = mp.Queue()
        self._proc = mp.Process(target=self._syncronize)
        self._detectPort()

    def startMonitoring(self):
        self._proc.start()

    def stopMonitoring(self):
        self._syncQueue.put("stop")
        while not self._timeQueue.empty():
            self._timeQueue.get()
        self._proc.join()

    def getNextTimestamp(self):
        if not self._timeQueue.empty():
            return self._timeQueue.get(False)
        else:
            return None

    def _detectPort(self):
        # find Arduino com port
        self._port = findSerialDevice(self.DEFAULT_VID, self.DEFAULT_PID)
        
        # if arduino com port not found, exit with error
        if self._port is None:
            raise Exception('Arduino %04x:%04x not detected' % (self.DEFAULT_VID, self.DEFAULT_PID))

        self._baud = self.DEFAULT_BAUD

    def _syncronize(self):
        # start serial connection with the arduino
	print 'Opening port', self._port
        serPort = serial.Serial(self._port, self._baud)

        # Verify that the connection has started
        for i in range(0, 10):
            line = serPort.readline().strip()
            print 'Arduino line (1): "%s"' % line
            if line.lower() == 'sync':
                print 'Got Arduino sync message'
                break

        print 'Arduino synchronization done'

        # Sync times between arduino and the computer
        serPort.write('*')   # tells the arduino to send back how much time has passed since it began to run
        localStartTime = datetime.datetime.now()
        remoteStartStr = serPort.readline()
        print 'Arduino line (2): "%s"' % remoteStartStr
        remoteStartTime = int(remoteStartStr.strip())
        setTime = datetime.timedelta(microseconds=remoteStartTime*1000)

        # Capture and save the time of each shot to a file
        while True:
            try:
                self._syncQueue.get(False)
                break
            except:
                pass

            remoteTime = int(serPort.readline().strip())

            print 'Arduino remote time:', remoteTime

            shotTime = localStartTime + datetime.timedelta(microseconds=remoteTime*1000) - setTime
            self._timeQueue.put(shotTime)

        serPort.close()
