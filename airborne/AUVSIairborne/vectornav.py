#!/usr/bin/env python
import serial
from struct import unpack, calcsize
from datetime import datetime, timedelta
import multiprocessing as mp
import Queue
from sortedcontainers import SortedDict
import json
from serial_helper import findSerialDevice
import sys
import math

try:
    import global_settings as gs
    TIMESTAMP_SIGNATURE = gs.BASE_TIMESTAMP
except:
    TIMESTAMP_SIGNATURE = ''


class VectorNav(object):
    TIMEOUT = 0.5 # Serial read timeout, in seconds

    MODE_SYNC = 0
    MODE_ASYNC = 1

    CHECKSUM_8BIT = 0
    CHECKSUM_16BIT = 1

    INITIAL_CRC = 0

    REG_USER_TAG = 0
    REG_MODEL_NUM = 1
    REG_HARDWARE_REV = 2
    REG_SERIAL_NUM = 3
    REG_FIRMWARE_VER = 4
    REG_SERIAL_BAUD = 5
    REG_ASYNC_DOUT_TYPE = 6
    REG_ASYNC_DOUT_FREQ = 7
    REG_PROTO_CTRL = 30
    REG_SYNC_CTRL = 32
    REG_SYNC_STATUS = 33
    REG_BIN_OUT_1 = 75
    REG_BIN_OUT_2 = 76
    REG_BIN_OUT_3 = 77

    FIX_NONE = 0
    FIX_TIME = 1
    FIX_2D = 2
    FIX_3D = 3

    SRC_VECTORNAV = 'VectorNav'

    DEFAULT_BAUD = 115200
    BINARY_OUTPUT_RATE_DIV = 32 # 800Hz/32 = 25Hz

    STATE_TIMEOUT = timedelta(seconds=60)

    DEFAULT_VID = 0x0403
    DEFAULT_PID = 0x6001

    FIELDS = {
        0: {
            0: ('TimeStartup', '<Q'),
            1: ('TimeGps', '<Q'),
            2: ('TimeSyncIn', '<Q'),
            3: ('Ypr', '<3f'),
            4: ('Qtn', '<4f'),
            5: ('AngularRate', '<3f'),
            6: ('PosLla', '<3d'),
            7: ('VelNed', '<3f'),
            8: ('Accel', '<3f'),
            9: ('Imu', '<3f3f'),
            10: ('MagPres', '<5f'),
            11: ('DeltaThetaVel', '<7f'),
            12: ('InsStatus', '<H'),
            13: ('SyncInCnt', '<L'),
            14: ('TimeGpsPps', '<Q')
        },
        1: {
            0: ('TimeStartup', '<Q'),
            1: ('TimeGps', '<Q'),
            2: ('GpsTow', '<Q'),
            3: ('GpsWeek', '<H'),
            4: ('TimeSyncIn', '<Q'),
            5: ('TimeGpsPps', '<Q'),
            6: ('TimeUTC', '<bBBBBBH'),
            7: ('SyncInCnt', '<L')
        },
        2: {
            0: ('ImuStatus', '<H'),
            1: ('UncompMag', '<3f'),
            2: ('UncompAccel', '<3f'),
            3: ('UncompGyro', '<3f'),
            4: ('Temp', '<f'),
            5: ('Pres', '<f'),
            6: ('DeltaTheta', '<4f'),
            7: ('DeltaV', '<3f'),
            8: ('Mag', '<3f'),
            9: ('Accel', '<3f'),
            10: ('AngularRate', '<3f'),
            11: ('SensSat', '<H')
        },
        3: {
            0: ('TimeUTC', '<bBBBBBH'),
            1: ('GpsTow', '<Q'),
            2: ('GpsWeek', '<H'),
            3: ('NumSats', '<B'),
            4: ('Fix', '<B'),
            5: ('GpsPosLla', '<3d'),
            6: ('GpsPosEcef', '<3d'),
            7: ('GpsVelNed', '<3f'),
            8: ('GpsVelEcef', '<3f'),
            9: ('GpsPosU', '<3f'),
            10: ('GpsVelU', '<f'),
            11: ('TimeU', '<L')
        },
        4: {
            0: ('VpeStatus', '<H'),
            1: ('Ypr', '<3f'),
            2: ('Qtn', '<4f'),
            3: ('DCM', '<9f'),
            4: ('MagNed', '<3f'),
            5: ('AccelNed', '<3f'),
            6: ('LinearAccelBody', '<3f'),
            7: ('LinearAccelNed', '<3f'),
            8: ('YprU', '<3f')
        },
        5: {
            0: ('InsStatus', '<H'),
            1: ('PosLla', '<3d'),
            2: ('PosEcef', '<3d'),
            3: ('VelBody', '<3f'),
            4: ('VelNed', '<3f'),
            5: ('VelEcef', '<3f'),
            6: ('MagEcef', '<3f'),
            7: ('AccelEcef', '<3f'),
            8: ('LinearAccelEcef', '<3f'),
            9: ('PosU', '<f'),
            10: ('VelU', '<f')
        }
    }

    def __init__(self, port, baud):
        self._port = port
        self._baud = baud
        self._serial = None
        self._csum_mode = self.CHECKSUM_8BIT
        self._state = {}
        self._tstate = SortedDict()
        self._proc = None
        self._mode = self.MODE_SYNC
        self._offsetYPR = None
        self._autocal = True

        m = datetime.now()

        self._tstate[m] = {}
        d = self._tstate[m]

        for g in self.FIELDS:
            for f in self.FIELDS[g]:
                self._state[self.FIELDS[g][f][0]] = None
                d[self.FIELDS[g][f][0]] = None

    @staticmethod
    def create():
        port = findSerialDevice(VectorNav.DEFAULT_VID, VectorNav.DEFAULT_PID)

        if port is None:
            raise Exception('VectorNav FTDI converter not detected')

        return VectorNav(port, VectorNav.DEFAULT_BAUD)

    def calibrate(self):
        view = self.getView()

        self._offsetYPR = view.YPR

    def open(self, mode):
        self.close()

        if mode != self.MODE_SYNC and mode != self.MODE_ASYNC:
            return

        self._mode = mode

        if mode == self.MODE_ASYNC:
            self._queueState = mp.Queue()
            self._queueSync = mp.Queue()
            self._proc = mp.Process(target=self._processFunc)
            self._proc.start()
        else:
            self._queueState = None
            self._queueSync = None
            self._proc = None
            self._openPort()

    def close(self):
        if self._mode == self.MODE_ASYNC:
            if self._proc is None:
                return

            self._queueSync.put(None)
            self._syncState()
            self._proc.join()
            self._proc = None
        else:
            if self._serial is None:
                return

            self._closePort()

        self._queueState = None
        self._queueSync = None
        self._mode = self.MODE_SYNC

    def _openPort(self):
        self._serial = serial.Serial(self._port, self._baud, timeout=self.TIMEOUT)
        self._configBinaryOutput(0, 'TimeUTC', 'Ypr', 'PosLla', 'VelNed', 'TimeUTC', 'NumSats', 'Fix', 'PosU', 'VelU', 'TimeU')

    def _closePort(self):
        self._serial.close()
        self._serial = None

    def _processFunc(self):
        self._openPort()

        while True:
            try:
                try:
                    self._queueSync.get(False)
                    break
                except Queue.Empty:
                    pass

                self._recvResponse()

            except KeyboardInterrupt: # Allow Ctrl+C without raising an exception
                break
            except: # Allow other exceptions
                pass

        self._closePort()

    def _send(self, data):
        self._serial.write(data)

    def _recv(self, size):
        return self._serial.read(size)

    def _recvLine(self):
        return self._serial.readline()

    @staticmethod
    def _calcChecksum8(cmd):
        csum = 0

        for c in cmd:
            csum ^= ord(c)

        return '%02X' % (csum & 0xFF)

    @staticmethod
    def _appendCRC(crc, data):
        for c in data:
            crc = ((crc >> 8) & 0xFF) | (crc << 8)
            crc ^= ord(c) & 0xFF
            crc ^= (crc & 0xFF) >> 4
            crc ^= crc << 12
            crc ^= (crc & 0xFF) << 5

        return crc & 0xFFFF

    @staticmethod
    def _calcChecksum16(cmd):
        return '%04X' % VectorNav._appendCRC(VectorNav.INITIAL_CRC, cmd)

    def _calcChecksum(self, cmd):
        if self._csum_mode == self.CHECKSUM_16BIT:
            return VectorNav._calcChecksum16(cmd)
        return VectorNav._calcChecksum8(cmd)

    def _sendCommand(self, id, params):
        cmd = 'VN' + id

        if len(params) > 0:
            cmd += ',' + ','.join(str(p) for p in params)

        cmd = '$' + cmd + '*' + self._calcChecksum(cmd) + '\r\n'

        self._send(cmd)

    def process(self, flush=False):
        if self._mode == self.MODE_SYNC:
            if flush:
                self._serial.flushInput() # Flush the input buffer

            self._waitResponse('$B') # Wait for a binary response

    def _waitResponse(self, id, process_func=None):
        while True:
            r = self._recvResponse()

            if r:
                if id is not None and r[0] == id:
                    return process_func(r) if process_func is not None else True
                elif r[0] == 'ERR':
                    return None

                return True

    def _processTextResponse(self, id, params):
        if id == 'GGA':
            pass

    def _recvResponse(self):
        sync = self._recv(1)

        if len(sync) < 1:
            return None

        if sync[0] == '$':
            line = str(self._recvLine())

            if line:
                return self._parseTextResponse(line)

        elif sync[0] == '\xFA':
            return self._parseBinaryResponse()

        return None

    def _parseTextResponse(self, line):
        if len(line) < 5:
            return None

        hdr = line[0:2]
        id = line[2:5]

        if hdr != 'VN':
            return None

        term = line.rfind('*')

        if term < 5:
            return None

        # TODO: Verify checksum

        params = line[5:term].split(',')

        self._processTextResponse(id, params)

        return (id, params)

    def _parseBinaryResponse(self):
        groups = self._recv(1)

        if len(groups) < 0:
            return None

        now = datetime.now()
        crc = VectorNav._appendCRC(self.INITIAL_CRC, groups)

        groups, = unpack('<B', groups)
        fields = []

        for g in range(0, 6):
            if (groups & (1 << g)) != 0:
                group_fields = self._recv(2)

                if len(group_fields) < 2:
                    return None

                crc = VectorNav._appendCRC(crc, group_fields)

                group_fields, = unpack('<H', group_fields)

                for f in range(0, 16):
                    if (group_fields & (1 << f)) != 0:
                        fields.append((g, f))

        state = {}

        for f in fields:
            if not f[0] in self.FIELDS:
                continue

            group_fields = self.FIELDS[f[0]]

            if not f[1] in group_fields:
                continue

            field_info = group_fields[f[1]]

            size = calcsize(field_info[1])
            data = self._recv(size)

            if len(data) < size:
                return None

            crc = VectorNav._appendCRC(crc, data)
            state[field_info[0]] = unpack(field_info[1], data)

        # Receive the CRC
        ref_crc = self._recv(2)
        crc = VectorNav._appendCRC(crc, ref_crc)

        if crc != 0:
            return None # Bad CRC

        for st in state:
            self._setState(st, state[st], now)

        return ('$B', None)

    def _setState(self, id, value, timestamp):
        state = (id, value, datetime.now())

        if self._mode == self.MODE_ASYNC:
            self._queueState.put(state)
        else:
            self._updateState(state)

    def _syncState(self):
        if self._mode != self.MODE_ASYNC:
            return

        # Add new entries
        try:
            while True:
                self._updateState(self._queueState.get(False))

        except Queue.Empty:
            pass

        # Remove old entries
        keys = list(self._tstate.irange(minimum=None, maximum=datetime.now() - self.STATE_TIMEOUT, inclusive=(True, False)))

        for k in keys:
            try:
                del self._tstate[k]
            except:
                pass

    def _updateState(self, state):
        self._state[state[0]] = state[1]
        d = self._tstate.setdefault(state[2], {})
        d[state[0]] = state[1]

    def _registerRead(self, reg_id):
        self._sendCommand('RRG', [ reg_id ])
        return self._waitResponse('RRG', lambda r: r[1])

    def _registerWrite(self, reg_id, *args):
        params = [ reg_id ]
        params.extend(list(args))

        self._sendCommand('WRG', params)
        return self._waitResponse('WRG', lambda r: r[1])

    def _findField(self, id):
        for g in self.FIELDS:
            for f in self.FIELDS[g]:
                if self.FIELDS[g][f][0] == id:
                    return (g, f)

        return None

    def _configBinaryOutput(self, index, *fields):
        if index < 0 or index > 2:
            return

        groups = 0
        group_fields = [0, 0, 0, 0, 0, 0]

        for f in fields:
            field = self._findField(f)

            if field is None:
                continue

            groups |= 1 << field[0]
            group_fields[field[0]] |= 1 << field[1]

        args = [1, self.BINARY_OUTPUT_RATE_DIV, '%02X' % groups]
        args.extend('%04X' % x for x in filter(None, group_fields))
        args = tuple(args)

        self._registerWrite(self.REG_BIN_OUT_1 + index, *args)

    def getState(self, id, maxTime=None):
        self._syncState()

        keys = self._tstate.irange(minimum=None, maximum=maxTime, inclusive=(True, True), reverse=True)

        for k in keys:
            if id in self._tstate[k]:
                value = self._tstate[k][id]

                if id == 'Ypr' and value is not None:
                    if self._offsetYPR is not None:
                        value = (value[0] - self._offsetYPR[0], value[1] - self._offsetYPR[1], value[2] - self._offsetYPR[2])
                    elif self._autocal:
                        self._offsetYPR = value
                        value = (0, 0, 0)

                if value is not None and len(value) == 1:
                    value = value[0]

                return value

        return None

    def getView(self, timestamp=None):
        if len(self._tstate) == 0:
            return None

        try:
            if timestamp is None:
                maxTime = self._tstate.iloc[-1]
            else:
                maxTime = next(self._tstate.irange(minimum=None, maximum=timestamp, inclusive=(True, True), reverse=True))

            return VectorNav.View(self, maxTime)
        except:
            #log.log('Error getting VectorNav view for timestamp {time}'.format(time=timestamp))
            print 'Error getting VectorNav view for timestamp {time}'.format(time=timestamp)
            return None

    class View(object):
        def __init__(self, vn, maxTime):
            self._vn = vn
            self._maxTime = maxTime

        def getState(self, id):
            return self._vn.getState(id, self._maxTime)

        @property
        def timeUTC(self):
            t = self.getState('TimeUTC')

            time = t[0]

            if time is None:
                return None

            return (datetime(2000 + time[0], time[1] + 1, time[2] + 1, time[3], time[4], time[5], time[6] * 1000), t[1])

        @property
        def position(self):
            """Get the latest position as (latitude, longitude, altitude)"""
            return self.getState('PosLla')

        @property
        def velocity(self):
            """Get the latest velocity in NED frame in m/s"""
            return self.getState('VelNed')

        @property
        def YPR(self):
            """Get the latest yaw/pitch/roll values in degrees"""
            return self.getState('Ypr')

        @property
        def numSats(self):
            """Get the latest number of visible satellites"""
            return self.getState('NumSats')

        @property
        def fix(self):
            """Get the latest GPS fix type"""
            return self.getState('Fix')

        @property
        def dict(self):
            """Get the data dictionary"""
            d = {
                'yaw': 0,
                'pitch': 0,
                'roll': 0,
                'src_att': None,
                'hdg': 0,
                'src_hdg': None,
                'lat': 0,
                'lon': 0,
                'relative_alt': 0,
                'src_gps': None,
                'cog': 0,
                'src_cog': None
            }

            ypr = self.YPR
            pos = self.position
            vel = self.velocity

            if ypr is not None:
                d['yaw'] = math.radians(ypr[0])
                d['pitch'] = math.radians(ypr[1])
                d['roll'] = math.radians(ypr[2])
                d['hdg'] = ypr[0] * 100
                d['src_att'] = VectorNav.SRC_VECTORNAV
                d['src_hdg'] = VectorNav.SRC_VECTORNAV

            if pos is not None and abs(pos[0]) > 1.0 and abs(pos[1]) > 1.0:
                d['lat'] = pos[0] * 1e7
                d['lon'] = pos[1] * 1e7
                d['relative_alt'] = pos[2] * 1e3
                d['src_gps'] = VectorNav.SRC_VECTORNAV

            d['fd_timestamp'] = self._maxTime.strftime(TIMESTAMP_SIGNATURE)
            #d['cog'] = atan2(vel[1], vel[0])
            d['src'] = VectorNav.SRC_VECTORNAV

            return d

        @property
        def json(self):
            """Get the json-encoded data"""
            return json.dumps(self.dict)


def main():
    if len(sys.argv) < 2:
        print 'Usage: python vectornav.py <sync|async> [com-port] [baud-rate]'
        return

    port = None
    baud = VectorNav.DEFAULT_BAUD

    if len(sys.argv) > 2:
        port = sys.argv[2]

    if len(sys.argv) > 3:
        baud = int(sys.argv[3])

    mode_str = sys.argv[1]

    if port is not None:
        vn = VectorNav(port, baud)
    else:
        vn = VectorNav.create()

    if mode_str != 'sync' and mode_str != 'async':
        print 'Unknown mode "%s"' % mode_str
        return

    mode = VectorNav.MODE_ASYNC if mode_str == 'async' else VectorNav.MODE_SYNC

    try:
        start = datetime.now()

        vn.open(mode)

        while True:
            if mode == VectorNav.MODE_SYNC:
                vn.process(False)

            view = vn.getView()

            if view is None:
                break

            #print 'Pos:', vn.position, 'Vel:', vn.velocity, 'YPR:', vn.YPR, 'Time:', vn.timeUTC, 'Sats:', vn.numSats
            #print 'YPR:', vn.YPR, 'Time:', vn.timeUTC
            print 'YPR:', view.YPR
            #print 'Pos:', view.position, 'Sats:', view.numSats

            d = datetime.now() - start

    except KeyboardInterrupt:
        pass

    except:
        vn.close()
        raise

    vn.close()

if __name__ == '__main__':
    main()
