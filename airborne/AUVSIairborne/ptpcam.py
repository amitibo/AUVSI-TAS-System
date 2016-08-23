#!/usr/bin/python
from __future__ import division
from camera import BaseCamera
import socket
from datetime import datetime
import os.path
from multiprocessing import Queue
from struct import unpack
import multiprocessing as mp
from pexif import JpegFile
from select import select
from collections import defaultdict
from twisted.python import log
import pyptp
from flashsync import FlashSync
from zoom import ZoomController


VID_SONY = 0x054C
PID_SONY_A6000 = 0x094E
USE_FLASHSYNC = True
USE_ZOOM = False

class PTPCamera(BaseCamera):
    @classmethod
    def createDefault(cls, targetPath, targetQueue=None):
        return cls(VID_SONY, PID_SONY_A6000, targetPath, targetQueue)

    def __init__(self, vid, pid, targetPath, targetQueue=None):
        #super(PTPCamera, self).__init__()
        log.msg('Initializing PTP camera')

        self.targetPath = targetPath
        self.targetQueue = targetQueue
        self._camera = pyptp.Camera(vid=vid, pid=pid, image_dir=targetPath, callback=self.onImageAdded)
        self._camera.handshake()
        self._camera.setparams(drive='low')
        self._shooting = False
        self._fs = None
        self._zc = None

        if USE_FLASHSYNC:
            try:
                self._fs = FlashSync()
                self._fs.startMonitoring()
            except:
                log.msg('WARNING: Could not initialize FlashSync')
                self._fs = None

        if USE_ZOOM:
            try:
                self._zc = ZoomController()
            except:
                log.msg('WARNING: Could not initialize zoom controller')
                self._zc = None

        #self._isoChanged = False
        #self._shutterChanged = False
        #self._apertureChanged = False
        self._prevZoom = 0

    def __del__(self):
        if self._fs is not None:
            self._fs.stopMonitoring()

    def startShooting(self):
        log.msg('------------------------------')
        log.msg('Starting to shoot')

        try:
            log.msg('Camera battery level: %d%%' % self._camera.getbattery())
        except Exception as e:
            log.err(e, 'Could not get camera battery level')

        try:
            self._camera.start()
            self._shooting = True
        except Exception as e:
            log.err(e, 'Failed starting')

        log.msg('------------------------------')

    def stopShooting(self):
        log.msg('------------------------------')
        log.msg('Stopping shooting')

        try:
            self._camera.stop()
            self._shooting = False
        except Exception as e:
            log.err(e, 'Failed stopping')

        try:
            log.msg('Camera battery level: %d%%' % self._camera.getbattery())
        except Exception as e:
            log.err(e, 'Could not get camera battery level')

        log.msg('------------------------------')

    def isShooting(self):
        return self._shooting;

    def setParams(self, **kwds):
        super(PTPCamera, self).setParams(**kwds)

        log.msg('Setting PTP camera parameters:')
        for name, value in kwds.items():
            log.msg('   {0} = {1}'.format(name, value))

        if 'ISO' in kwds:
            #self._isoChanged = True
            log.msg('Setting ISO to %s' % str(self.ISO))
            try:
                self._camera.setparams(iso=self.ISO)
                log.msg('Setting ISO succeeded')
            except:
                log.msg('Setting ISO failed')

        if 'aperture' in kwds:
            #self._apertureChanged = True
            log.msg('Setting aperture to %s' % str(self.aperture / 10))
            try:
                self._camera.setparams(fnumber=self.aperture / 10)
                log.msg('Setting aperture succeeded')
            except:
                log.msg('Setting aperture failed')

        if 'shutter' in kwds:
            #self._shutterChanged = True
            log.msg('Setting shutter speed to 1/%s' % str(self.shutter))
            try:
                self._camera.setparams(shutter=(1, self.shutter))
                log.msg('Setting shutter speed succeeded')
            except:
                log.msg('Setting shutter speed failed')

        if self._zc is not None and 'zoom' in kwds:
            if self.zoom != self._prevZoom:
                self._prevZoom = self.zoom
                zoomIn = (self.zoom > 1)
                zoomStr = 'in' if zoomIn else 'out'

                log.msg('Zooming %s' % zoomStr)
                try:
                    self._zc.zoom(zoomIn)
                    log.msg('Zoom succeeded')
                except:
                    log.msg('Zoom failed')

        #self._syncParams()

    def onImageAdded(self, path):
        log.msg('Image added: {path}'.format(path=path))

        time = None

        if self._fs is not None:
            time = self._fs.getNextTimestamp()

        if self.targetQueue:
            self.targetQueue.put((path, time), False)

    #def _syncParams(self):
    #    if self._isoChanged:
    #        self._camera.setISO(self.ISO)
    #        self._isoChanged = False
    #
    #    if self._shutterChanged:
    #        self._control.setShutterSpeed("1/" + str(self.shutter))
    #        self._shutterChanged = False
    #
    #    if self._apertureChanged:
    #        self._control.setAperture(self.aperture)
    #        self._apertureChanged = False

def createDefaultCamera():
    return PTPCamera.createDefault('/home/odroid/CameraPictures');
