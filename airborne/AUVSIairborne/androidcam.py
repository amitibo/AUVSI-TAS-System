#!/usr/bin/python
from __future__ import division
from camera import BaseCamera
import socket
from datetime import datetime
import os.path
from Queue import Queue
from struct import unpack
import multiprocessing as mp
from pexif import JpegFile
from select import select
from collections import defaultdict
from twisted.python import log

class AndroidCamera(BaseCamera):
    @classmethod
    def createDefault(cls, targetPath, targetQueue):
        return cls("192.168.42.129", 9995, 9996, targetPath, targetQueue)

    def __init__(self, addr, controlPort, dataPort, targetPath, targetQueue):
        #super(AndroidCamera, self).__init__()
        log.msg('Initializing android camera')

        self._images = None
        self._sock = None
        self._receiver = None
        self._storage = None
        self._control = None
        self.addr = addr
        self.controlPort = controlPort
        self.dataPort = dataPort
        self.targetPath = targetPath
        self.targetQueue = targetQueue
        self._zoomChanged = True
        self._isoChanged = True
        self._shutterChanged = True
        self._apertureChanged = True
        self._enableParams = True #False #True

    def startShooting(self):
        if self._control is not None:
            # Already shooting
            return

        self.stopShooting()

        self._images = mp.Queue()
        self._control = ControlThread(self.addr, self.controlPort)
        self._receiver = ReceiverThread(self._images, self.addr, self.dataPort)
        self._storage = StorageThread(self._images, self.targetPath, self.targetQueue)

        if self._enableParams:
            self._control.start()

        self._receiver.start()
        self._storage.start()

        self._syncParams()

    def isShooting(self):
        return self._control is not None

    def stopShooting(self):
        if self._receiver is not None:
            self._receiver.stop()
            self._receiver = None

        if self._storage is not None:
            self._storage.stop()
            self._storage = None

        if self._control is not None:
            self._control.stop()
            self._control = None

    def setParams(self, **kwds):
        super(AndroidCamera, self).setParams(**kwds)

        log.msg('Setting android camera parameters:')
        for name, value in kwds.items():
            log.msg('   {0} = {1}'.format(name, value))

        if 'zoom' in kwds:
            self._zoomChanged = True
            log.msg('Setting zoom to %s' % str(self.zoom))
            #self._control.setZoom(self.zoom)

            #try:
            #    control = ControlThread(self.addr, self.controlPort)
            #    control.start()
            #    control.setZoom(self.zoom)
            #    control.syncStop()
            #except Exception as e:
            #    print 'Error: %s' % str(e)

        if 'ISO' in kwds:
            self._isoChanged = True
            log.msg('Setting ISO to %s' % str(self.ISO))

        if 'aperture' in kwds:
            self._apertureChanged = True
            log.msg('Setting aperture to %s' % str(self.aperture))

        if 'shutter' in kwds:
            self._shutterChanged = True
            log.msg('Setting shutter speed to 1/%s' % str(self.shutter))

        self._syncParams()

    def _syncParams(self):
        if self._control is None or not self._enableParams:
            return

        if self._zoomChanged:
            self._control.setZoom(self.zoom)
            self._zoomChanged = False

        if self._isoChanged:
            self._control.setISO(self.ISO)
            self._isoChanged = False

        if self._shutterChanged:
            self._control.setShutterSpeed("1/" + str(self.shutter))
            self._shutterChanged = False

        if self._apertureChanged:
            self._control.setAperture(self.aperture)
            self._apertureChanged = False

class StoppableThread(mp.Process):
    def __init__(self):
        super(StoppableThread, self).__init__()
        #self._stop = Event()
        self._queue = mp.Queue(1)

    def stop(self):
        #self._stop.set()
        try:
            self._queue.put(None, False)
        except:
            pass

    def isStopped(self):
        #return self._stop.isSet()
        return not self._queue.empty()

class ReceiverThread(StoppableThread):
    def __init__(self, images, addr, port):
        super(ReceiverThread, self).__init__()
        self._images = images
        self._addr = addr
        self._port = port
        self.PACKET_MAGIC = 0xEE7EC015
        self.PACKET_MAGIC_SYNC = '\x15' # First received byte of PACKET_MAGIC

    def run(self):
        try:
            self._connect()

            while (not self.isStopped()) and self._receiveImage():
                pass

            self._disconnect()
        except Exception as e:
            log.err(e, 'Receiver thread')

    def _connect(self):
        log.msg("Receiver thread: Connecting to %s:%d..." % (self._addr, self._port))

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.connect((self._addr, self._port))

        log.msg("Receiver thread: Connected")

    def _disconnect(self):
        log.msg("Receiver thread: Disconnecting...")

        if self._sock is not None:
            self._sock.close()
            self._sock = None

        log.msg("Recevier thread: Disconnected")

    def _ackImage(self, id):
        try:
            self._sock.send('d' + str(id) + '\r\n')
        except Exception as e:
            log.err(e, 'Receiver thread: ackImage()')

    def _receiveImage(self):
        try:
            if not self._receiveSync():
                return False

            hdr = self._recvFull(20)

            if hdr is None:
                return False

            (id, index, timestamp, size) = unpack('<IIQI', hdr)

            data = self._recvFull(size)

            if data is None:
                return False

            dt = datetime.utcfromtimestamp(timestamp / 1000)

            #print 'Received image %d: Timestamp is %s' % (index + 1, dt.strftime('%H:%M:%S.%f')[:-3])
            log.msg('Received image %d: Timestamp is %s' % (index + 1, dt.strftime('%H:%M:%S.%f')[:-3]))

            self._images.put((id, index, dt, data))
            self._ackImage(id)

            return True
        except Exception as e:
            log.err(e, "Receiver thread: receiveImage()")
            return True # Keep receiving

    def _receiveSync(self):
        while True:
            sync = self._recvFull(1)
            if sync is None:
                return None

            if sync != self.PACKET_MAGIC_SYNC:
                continue

            syncCont = self._recvFull(3)

            if syncCont is None:
                return None

            sync += syncCont
            magic, = unpack('<I', sync)

            if magic == self.PACKET_MAGIC:
                return True

    def _recvFull(self, size):
        data = ''

        while len(data) < size:
            if self.isStopped():
                return None

            ready = select([self._sock], [], [], 0.5)

            if not ready:
                continue

            chunk = self._sock.recv(size - len(data))

            if len(chunk) == 0:
                return None

            data += chunk

        return data

class StorageThread(StoppableThread):
    def __init__(self, images, targetPath, targetQueue):
        super(StorageThread, self).__init__()
        self._images = images
        self._targetPath = targetPath
        self._targetQueue = targetQueue

    def run(self):
        try:
            while (not self.isStopped()) and self._saveImage():
                pass
        except Exception as e:
            log.err(e, 'Camera control thread')

    def stop(self):
        super(StorageThread, self).stop()
        self._images.put((None, None, None, None), False)

    def _saveImage(self):
        try:
            (id, index, dt, image) = self._images.get(True, None)

            if id is None:
                return False

            #jpeg = JpegFile.fromString(image)
            #jpeg.exif.primary.DateTime = dt.strftime('%Y:%m:%d %H:%M:%S %f')[:-3]

            path = os.path.join(self._targetPath, str(index + 1) + '.jpg')

            log.msg('Storing %s' % path)
            #print 'Storing "%s"' % path

            #jpeg.writeFile(path)

            with open(path, 'wb') as f:
                f.write(image)

            if self._targetQueue:
                log.msg('Notifying filesystem watcher: %s' % path)
                self._targetQueue.put((path, dt), False)

            return True
        except Exception as e:
            log.err(e, "Storage thread: saveImage()")
            return True # Keep storing

class ControlThread(StoppableThread):
    def __init__(self, addr, port):
        super(ControlThread, self).__init__()
        self._addr = addr
        self._port = port
        self._messages = mp.Queue()

    def run(self):
        try:
            log.msg("Camera control threa started")
            self._connect()

            while (not self.isStopped() and self._processMessage()):
                pass

            self._disconnect()
        except Exception as e:
            log.err(e, 'Camera control thread')

        self.stop()

    def stop(self):
        super(ControlThread, self).stop()
        self.syncStop()

    def syncStop(self):
        self._postMessage(None, None)

    def setZoom(self, zoom):
        self._postMessage('zoom', zoom)

    def setISO(self, iso):
        self._postMessage('iso', iso)

    def setShutterSpeed(self, shutter):
        self._postMessage('shutter', shutter)

    def setAperture(self, aperture):
        self._postMessage('aperture', aperture)

    def setFocus(self, focus):
        self._postMessage('focus', focus)

    def _sendZoom(self, zoom):
        self._send('z' + str(zoom))

    def _sendISO(self, iso):
        self._send('i' + str(iso))

    def _sendShutterSpeed(self, shutter):
        self._send('s' + str(shutter))

    def _sendAperture(self, aperture):
        self._send('a' + str(aperture))

    def _sendFocus(self, focus):
        focus = focus.lower()

        if focus == 'auto':
            focus = 'a'
        elif focus == 'inf' or focus == 'infinite':
            focus = 'i'
        elif focus == 'macro':
            focus = 'm'
        elif focus == 'fixed':
            focus = 'f'
        else:
            return

        self._send('f' + focus)

    def _postMessage(self, key, value):
        self._messages.put((key, value), False)

    def _connect(self):
        log.msg("Camera control thread: Connecting to %s:%d..." % (self._addr, self._port))

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.connect((self._addr, self._port))

        log.msg("Camera control thread: Connected")

    def _disconnect(self):
        log.msg("Camera control thread: Disconnecting...")
        if self._sock is not None:
            self._sock.close()
            self._sock = None

        log.msg("Camera control thread: Disconnected")

    def _send(self, data):
        log.msg("Camera control thread: Sending %d bytes: %s" % (len(data) + 2, data))
        self._sock.send(data + '\r\n')

    def _processMessage(self):
        _handlers = defaultdict(lambda: None, {
            'zoom': self._sendZoom,
            'iso': self._sendISO,
            'shutter': self._sendShutterSpeed,
            'aperture': self._sendAperture,
            'focus': self._sendFocus
        })

        (key, value) = self._messages.get(True, None)

        if key is None:
            return False

        _handlers[key](value)

        return True

def createDefaultCamera():
    return AndroidCamera("192.168.42.129", 9995, 9996, '/home/odroid/CameraPictures', None);
