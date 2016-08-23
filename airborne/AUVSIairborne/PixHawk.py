from __future__ import division
from twisted.internet import reactor, protocol, task, threads
from sortedcontainers import SortedDict
from twisted.python import log
from datetime import datetime
from serial_helper import findSerialDevice
import global_settings as gs
try:
    from pymavlink import mavutil
except:
    pass
import json
import os

SRC_PIXHAWK = 'PixHawk'
TIMESTAMP_SIGNATURE = gs.BASE_TIMESTAMP
DEFAULT_FLIGHTDATA = {
    'yaw': 0,
    'roll': 0,
    'pitch': 0,
    'src_att': None,
    'hdg': 0,
    'src_hdg': None,
    'timestamp': datetime.now().strftime(TIMESTAMP_SIGNATURE),
    'fd_timestamp': datetime.now().strftime(TIMESTAMP_SIGNATURE),
    'lon': 0,
    'lat': 0,
    'relative_alt': 0,
    'src_gps': None,
    'cog': 0,
    'src_cog': None,
    'src': SRC_PIXHAWK
}

def wait_heartbeat(m):
    """wait for a heartbeat so we know the target system IDs"""

    log.msg("Waiting for APM heartbeat")
    m.wait_heartbeat()
    log.msg("Heartbeat from APM (system %u component %u)" % (m.target_system, m.target_system))


continue_messages = True

def monitorMessages(m, rate):
    """show incoming mavlink messages"""

    _send_data_request(m, rate)

    data_flags = {}
    flight_data = {}
    while continue_messages:
        msg = m.recv_match(blocking=True)
        if not msg or msg.get_type() == "BAD_DATA":
            continue

        if msg.get_type() == "ATTITUDE":
            flight_data['yaw'] = msg.yaw
            flight_data['roll'] = msg.roll
            flight_data['pitch'] = msg.pitch
            flight_data['src_att'] = SRC_PIXHAWK
            # elif msg.get_type() == "SYSTEM_TIME":              """not important: checking timestamp- 08.06"""
            # flight_data['pixhawktime'] = msg.time_unix_usec
        elif msg.get_type() == "GLOBAL_POSITION_INT":
            t = datetime.now()
            flight_data['fd_timestamp'] = t.strftime(TIMESTAMP_SIGNATURE)
            flight_data['timestamp'] = flight_data['fd_timestamp']
            flight_data['lon'] = msg.lon
            flight_data['lat'] = msg.lat
            flight_data['relative_alt'] = msg.relative_alt
            flight_data['hdg'] = msg.hdg
            flight_data['src_hdg'] = SRC_PIXHAWK
            flight_data['src_gps'] = SRC_PIXHAWK

        elif msg.get_type() == "GPS_RAW_INT":
            flight_data['cog'] = msg.cog
            flight_data['src_cog'] = SRC_PIXHAWK

        if 'yaw' in flight_data and 'lon' in flight_data \
                                                      and 'cog' in flight_data:
            flight_data['src'] = SRC_PIXHAWK
            path = os.path.join(gs.FLIGHT_DATA_FOLDER, "{timestamp}.json".format(timestamp=flight_data['timestamp']))
            with open(path, 'wb') as f:
                json.dump(flight_data, f)

            reactor.callFromThread(addPHdata, flight_data)
            flight_data = {}


def addPHdata(flight_data):
    """Add new flight data message to the records"""

    global flight_data_log

    flight_data_log[flight_data['timestamp']] = flight_data


def queryPHdata(timestamp):
    """Query the closest flight data records to some timestamp"""

    if len(flight_data_log.values()) == 0:
        return DEFAULT_FLIGHTDATA

    index = flight_data_log.bisect(timestamp)

    r_index = max(index-1, 0)
    l_index = min(index, len(flight_data_log))

    #
    # TODO interpolate the sorrounding flight data records.
    #
    return flight_data_log.values()[r_index]#, flight_data_log.values()[l_index]


def initPixHawk(device=None, baudrate=115200, rate=4):
    """Start the thread that monitors the PixHawk Mavlink messages.

    Parameters
    ----------
    device: str
        Address of serialport device.
    baudrate: int
        Serialport baudrate (defaults to 57600)
    rate: int
        Requested rate of messages.
    """

    global flight_data_log
    flight_data_log = SortedDict()

    if device is None:
        device = findSerialDevice(0x067B, 0x2303)
        if device is None:
            raise Exception('PixHawk controller %04x:%04x not detected' % (0x067B, 0x2303))

    #
    # Create the auvsi data folder.
    #
    if not os.path.exists(gs.AUVSI_BASE_FOLDER):
        os.makedirs(gs.AUVSI_BASE_FOLDER)
    if not os.path.exists(gs.FLIGHT_DATA_FOLDER):
        os.makedirs(gs.FLIGHT_DATA_FOLDER)

    #
    # create a mavlink serial instance
    #
    master = mavutil.mavlink_connection(device, baud=baudrate)

    #
    # Start the messages thread
    #
    d = threads.deferToThread(monitorMessages, master, rate)


def _send_data_request(master, rate):
    #
    # wait for the heartbeat msg to find the system ID
    #
    wait_heartbeat(master)
    #
    # Setting requested streams and their rate.
    #
    log.msg("Sending all stream request for rate %u" % rate)
    for i in range(3):
        master.mav.request_data_stream_send(
            master.target_system,
            master.target_component,
            mavutil.mavlink.MAV_DATA_STREAM_ALL,
            rate,
            1
        )


def initPixHawkSimulation():
    import glob

    global flight_data_log

    flight_data_log = SortedDict()

    base_path = os.environ['AUVSI_CV_DATA']
    log_paths = glob.glob(os.path.join(base_path, 'flight_data', '*.json'))

    for path in sorted(log_paths):
        with open(path, 'rb') as f:
            flight_data = json.load(f)
            ph_flight_data = flight_data['all']['PixHawk']
            timestamp = os.path.split(path)[1][:-5]
            ph_flight_data['timestamp'] = timestamp
            try:
                ph_flight_data['pitch'] = flight_data['all']['VectorNav']['pitch']
                ph_flight_data['roll'] = flight_data['all']['VectorNav']['roll']
            except:
                pass
            addPHdata(ph_flight_data)


def stopPixHawk():

    global continue_messages

    continue_message = False


if __name__ == '__main__':

    #try:
        #initPixHawk()
        #reactor.run()
    #except:
        #stopPixHawk()
        #raise

    import AUVSIcv

    initPixHawkSimulation()

    base_path = os.environ['AUVSI_CV_DATA']
    imgs_paths = glob.glob(os.path.join(base_path, '*.jpg'))


    img = AUVSIcv.Image(imgs_paths[0])
    print queryPHdata(img.datetime)
