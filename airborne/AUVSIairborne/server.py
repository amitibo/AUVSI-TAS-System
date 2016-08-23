from twisted.internet import reactor, threads
from twisted.web.resource import Resource, NoResource
from twisted.python import filepath
from twisted.web.server import Site
from twisted.web.static import File
from twisted.python import log
from twisted.python.logfile import DailyLogFile
from twisted.internet.protocol import Factory
from twisted.protocols.basic import LineReceiver
from twisted.internet.protocol import Factory, Protocol
from twisted.python.threadpool import ThreadPool
import threading
import thread
from multiprocessing import Queue
import requests
from vectornav import VectorNav
import pkg_resources
try:
    from shapely.geometry import Polygon, Point
    HAS_SHAPELY = True
except:
    HAS_SHAPELY = False

from txzmq import ZmqEndpoint, ZmqFactory, ZmqPushConnection, ZmqPullConnection, ZmqREPConnection, ZmqConnection
from zmq import constants

from AUVSIairborne.camera import SimulationCamera, CanonCamera
from AUVSIairborne.androidcam import AndroidCamera
from datetime import datetime
import global_settings as gs
import AUVSIairborne.images as IM
import AUVSIairborne.PixHawk as PH
import AUVSIcv
import platform
import traceback
from PIL import Image
import json
from sys import stdout
import pickle
import uuid
import zmq
import cv2
import os

import Queue as tQueue


__all__ = (
    'start_server'
)

ADLC_TEST_IMAGE_COUNT = 10
SAMPLE_IMAGE_COUNT = 1
MINTHREADS = 10
MAXTHREADS = 10

JETSON_IP = '192.168.1.102'
ADLC_PROCESS_URL = 'http://{ip}:8000/process'.format(ip=JETSON_IP)
ADLC_RX_PORT = 5558
ADLC_SAMPLE_IMAGE_COUNT = 10
ADLC_UPLOAD_EVERY = 2


def upload_thread(upload_queue):
    """A thread for uploading captured images."""

    upload_cnt = 0
    
    while True:
        #
        # Wait for a new upload
        #
        img_path, flight_data = upload_queue.get()

        #
        # Check if time to quit
        #
        if img_path is None:
            log.msg('Upload thread stopped')
            break

        upload_cnt = (upload_cnt + 1) % ADLC_UPLOAD_EVERY
        if upload_cnt != 0:
            log.msg('Skipping ADLC frame (uploading 1 every {} frames).'.format(ADLC_UPLOAD_EVERY))
            continue
        
        try:
            log.msg('Sending image to ADLC server')
            with open(img_path, 'rb') as f:
                requests.post(ADLC_PROCESS_URL, files={'imagefile': f, 'json': json.dumps(flight_data)})

        except Exception as e:
            log.err(e, 'Failed sending to ADLC server')


class ControlCmdError(Exception):
    def __init__(self, error):
        self.value = error

    def __str__(self):
        return 'ERROR - '+repr(self.value)


class ImageFileServerConnection(ZmqREPConnection):
    """Handle requests for images."""

    def __init__(self, factory, endpoint):
        ZmqREPConnection.__init__(self, factory, endpoint=endpoint)

    def gotMessage(self, messageId, *messageParts):
        rep = self.createMessageData(messageParts[0])
        self.reply(messageId, *rep)

    def createMessageData(self, image_basename):
        image_name = image_basename + '.jpg'
        flightdata_name = image_basename + '.json'
        image_path = os.path.join(gs.RESIZED_IMAGES_FOLDER, image_name)
        flightdata_path = os.path.join(gs.RESIZED_IMAGES_FOLDER, flightdata_name)

        image_data = ""
        flight_data = {}

        try:
            with open(image_path, 'rb') as f:
                image_data = f.read()

            try:
                with open(flightdata_path, 'r') as f:
                    flight_data = json.load(f)
            except:
                log.msg("Could not find flight data {fd}".format(fd=flightdata_path))
        except:
            log.msg("Could not find image {img}".format(img=image_name))

        return gs.RESIZED_IMAGE, image_name, image_data, json.dumps(flight_data)


class ImagesServer(object):
    """The main server of the airborne computer.

    Manages the camera and the communication with the ground computer and
    ADLC onboard computer.
    """

    def __init__(self, zmq_notice_port, zmq_files_port, vn=None):

        self._loadSearchArea()

        #
        # Setup the zmq socket used for sending notice of images.
        #
        zmq_factory = ZmqFactory()
        endpoint = ZmqEndpoint('bind', 'tcp://*:{zmq_port}'.format(zmq_port=zmq_notice_port))
        self.zmq_socket = ZmqPushConnection(zmq_factory, endpoint)

        #
        # Setup the zmq socket used for sending the images.
        #
        endpoint = ZmqEndpoint('bind', 'tcp://*:{zmq_port}'.format(zmq_port=zmq_files_port))
        self.zmq_files_socket = ImageFileServerConnection(zmq_factory, endpoint, )

        #
        # Setup the zmq socket used for receiving detection results from the
        # jetson.
        #
        endpoint_rx = ZmqEndpoint('connect', 'tcp://{ip}:{port}'.format(ip=JETSON_IP, port=ADLC_RX_PORT))
        self.adlc_rx_socket = ZmqPullConnection(zmq_factory, endpoint_rx)
        self.adlc_rx_socket.onPull = self.handleADLCResults

        #
        # Flag that controls the sending the images
        #
        self._send_images = threading.Event()

        self.manual_crop_cnt = 0
        self.auto_crop_cnt = 0
        self._img_counter = 0
        self._adlc_count = 0
        self._received_image_count = 0

        self._vn = vn

        #
        # Start the upload thread.
        # Note:
        # I am using a separate thread for uploading in order to use an
        # upload queue. We had a problem where slow upload caused many upload
        # processes to start together and cause jamming in communication.
        #
        self.upload_queue = tQueue.Queue(0)
        self.upload_thread = thread.start_new_thread(upload_thread, (self.upload_queue,))

    def __del__(self):
        self.upload_queue.put((None, None))

    def _loadSearchArea(self):
        self._search_area = None

        if not HAS_SHAPELY:
            return

        #
        # Load the search area.
        #
        try:
            data_path = pkg_resources.resource_filename('AUVSIairborne', 'resources/search_area.txt')

            coords = []
            with open(data_path, 'rb') as f:
                for line in f:
                    line = line.strip()
                    if line == '':
                        continue

                    coords.append(tuple(float(val) for val in line.split()))

            self._search_area = Polygon(coords).buffer(gs.SEARCH_AREA_BUFFER_DEG)
        except Exception as e:
            log.err(e, 'Failed to load search area data')

    def sendADLCImage(self, path, flight_data):
        """Send a new image to the ADLC onboard computer."""

        if ADLC_PROCESS_URL:
            self.upload_queue.put((path, flight_data))

    def handleADLCResults(self, message):
        """Handle the analysis result sent back from the ADLC onboard computer."""

        path, results = pickle.loads(message[0])
        try:

            message_data = message[0]

            #
            # Push the results down to the ground station.
            #
            data = [gs.AUTO_ANALYSIS, message_data]
            self.zmq_socket.push(data)
            log.msg(
                "Finished sending Jetson results for image: {path}, found {num} ROIS.".format(
                    path=path,
                    num=len(results)
                )
            )
        except zmq.error.Again:
            log.msg("Skipping sending of Jetson results, no pull consumers...")

    def handleNewImage(self, path, timestamp=None):
        """Handle a new image received from the camera."""

        current_time = datetime.now()
        if timestamp is not None:
            img_time = timestamp
        else:
            img_time = current_time

        #
        # Handle the new image
        #
        img_path, resized_img_path, flight_data = IM.processImg(path, current_time, img_time, self._vn)
        resized_img_name = os.path.split(resized_img_path)[-1]

        send_to_adlc = True

        if self._received_image_count < ADLC_TEST_IMAGE_COUNT:
            # Send without filtering
            pass
        elif self._search_area is not None and 'src_gps' in flight_data \
            and 'lat' in flight_data and 'lon' in flight_data and flight_data['src_gps'] is not None:
            lat = flight_data['lat'] * 1e-7
            lon = flight_data['lon'] * 1e-7
            send_to_adlc = self._search_area.contains(Point(lat, lon))

            if send_to_adlc:
                log.msg('Image is inside search area, sending to ADLC server')
            else:
                log.msg('Image is outside search area, skipping sending to ADLC server')

        self._received_image_count += 1

        if send_to_adlc:
            try:
                self.sendADLCImage(
                    img_path if AUVSIcv.global_settings.ADLC_SEND_FULLSIZE else resized_img_path,
                    flight_data
                )
            except:
                log.err("Failed to send image to ADLC server.")

        #
        # Send the new image and flight_data
        #
        if self._send_images.isSet():
            if self._img_counter == 0:
                resized_img_basename = os.path.splitext(resized_img_name)[0]
                log.msg("Sending notification for {img}...".format(img=resized_img_basename))
                data = [ gs.RESIZED_IMAGE, resized_img_basename ]

                try:
                    log.msg("Started sending of {img}.".format(img=resized_img_name))
                    self.zmq_socket.push(data)
                    log.msg("Finished sending of {img}.".format(img=resized_img_name))

                except zmq.error.Again:
                    log.msg("Skipping sending of {img}, no pull consumers...".format(img=resized_img_name))

            self._img_counter += 1

            if self._img_counter >= SAMPLE_IMAGE_COUNT:
                self._img_counter = 0

    def handleCrop(self, img_name, coords, yaw, lat, lon, crop_type):
        """Handle the request for a new crop"""

        #
        # Get the crop.
        #
        crop_img = IM.handleNewCrop(img_name, coords)

        #
        # Set paths
        #
        base_path = gs.CROPS_FOLDER
        random_str = str(uuid.uuid4()).split('-')[-1]
        if crop_type == gs.MANUAL_CROP:
            crop_name = 'manual_%03d_%s.jpg' % (self.manual_crop_cnt, random_str)
            self.manual_crop_cnt += 1
        else:
            crop_name = 'auto_%03d_%s.jpg' % (self.auto_crop_cnt, random_str)
            self.auto_crop_cnt += 1

        crop_path = os.path.join(base_path, crop_name)

        #
        # Save the crop
        #
        cv2.imwrite(crop_path, crop_img)

        #
        # Send the crop and its data.
        #
        with open(crop_path, 'rb') as f:
            data = [crop_type, img_name]+[str(c) for c in coords]+[yaw, lat, lon, os.path.split(crop_path)[-1], f.read()]

        try:
            self.zmq_socket.push(data)
            log.msg("Finished sending of crop {crop_name}.".format(crop_name=crop_name))

        except zmq.error.Again:
            log.msg("Skipping sending of crop {crop_name}, no pull consumers...".format(crop_name=crop_name))

    def sendImages(self, new_state):
        """Control the state of sending images to the ground station"""

        if new_state:
            log.msg("Start downloading images")
            self._send_images.set()
        else:
            log.msg("Stop downloading images")
            self._send_images.clear()

        self.sendDownloadState()

    def sendFlightData(self):
        """Send flight data (telemetry) to the ground station."""

        fds = []
        time = datetime.now()

        #
        # Get positioning from the vectornav.
        #
        if self._vn is not None:
            view = self._vn.getView()

            if view is not None:
                fds.append(view.dict)

        #
        # Get telemetry from the PixHawk.
        #
        try:
            fds.append(PH.queryPHdata(time.strftime(gs.BASE_TIMESTAMP)))
        except:
            pass

        if len(fds) == 0:
            return

        try:
            flight_data = IM.mergeFlightData(fds)
            flight_data['timestamp'] = time.strftime(gs.BASE_TIMESTAMP)
        except:
            return

        #
        # Send the data down to the ground station.
        #
        try:
            self.zmq_socket.push([gs.FLIGHT_DATA, json.dumps(flight_data)])
        except zmq.error.Again:
            pass


    def sendDownloadState(self):
        self.zmq_socket.push([gs.STATE, gs.STATE_DOWNLOAD, gs.STATE_ON if self._send_images.isSet() else gs.STATE_OFF])

    def sendCameraState(self, shooting):
        self.zmq_socket.push([gs.STATE, gs.STATE_SHOOT, gs.STATE_ON if shooting else gs.STATE_OFF])

    def sendState(self, shooting):
        self.sendDownloadState()
        self.sendCameraState(shooting)

class SystemControlProtocol(LineReceiver):
    """Handle the control communication between ground station and airborne computer."""

    def __init__(self, factory, address):
        self.factory = factory
        self.address = address

    def connectionMade(self):
        host = {'ip': self.address.host, 'port': self.address.port}
        log.msg("Connection made by {ip}:{port}.".format(**host))
        self.sendLine("Connected to Airborne AUVSI")

    def connectionLost(self, reason):
        log.msg("Connection was Lost: '{}".format(str(reason)))

    def lineReceived(self, line):
        splits = line.strip().split()

        #
        # Split cmd line to cmd and params
        #
        if len(splits) > 1:
            cmd, params = splits[0], splits[1:]
        else:
            cmd, params = splits[0], []

        try:
            #
            # Handle 'camera' cmd.
            #
            if cmd == 'camera':
                if params[0] == 'start':
                    self.factory.camera.startShooting()
                elif params[0] == 'off':
                    self.factory.camera.stopShooting()
                elif params[0] == 'set':
                    items = params[1:]
                    params_dict = {key:int(val) for key, val in zip(items[::2], items[1::2])}
                    self.factory.camera.setParams(**params_dict)
                else:
                    raise ControlCmdError('Unknown "camera" parameters: "{params}"'.format(params=params))

                self.factory.images_server.sendCameraState(self.factory.camera.isShooting())

            #
            # Handle 'download' cmd.
            #
            elif cmd == 'download':
                if params[0] == 'start':
                    self.factory.images_server.sendImages(new_state=True)
                elif params[0] == 'off':
                    self.factory.images_server.sendImages(new_state=False)
                else:
                    raise ControlCmdError('Unknown "download" parameters: "{params}"'.format(params=params))

            #
            # Handle 'crop' cmd.
            #
            elif cmd == 'crop':
                if len(params) != 9:
                    raise ControlCmdError('Wrong "crop" params,: "{params}". Expecting "crop [img_name] [crop_type] yaw lat lon left top right bottom"'.format(params=params))

                img_name = params[0]
                crop_type = params[1]
                yaw = params[2]
                lat = params[3]
                lon = params[4]
                coords = [float(c) for c in params[5:]]

                #
                # Process the crop
                #
                self.factory.images_server.handleCrop(img_name, coords, yaw, lat, lon, crop_type)

            #
            # Handle calibration command.
            #
            elif cmd == 'calibrate':
                if len(params) != 1:
                    raise ControlCmdError('Wrong "calibrate" params,: "{params}". Expecting "calibrate <target>"'.format(params=params))

                log.msg('Got calibration command')

                if params[0] == 'camera':
                    log.msg('Calibrating camera')
                    self.factory.camera.calibrate()
                elif params[0] == 'imu' and self.factory.imu is not None:
                    log.msg('Calibrating IMU')
                    self.factory.imu.calibrate()

            elif cmd == 'state':
                self.factory.images_server.sendState(self.factory.camera.isShooting())

            else:
                raise ControlCmdError('Unknown cmd line: "{line}"'.format(line=line))

        except ControlCmdError as e:
            self.sendLine(e.value)
            return
        except:
            err = traceback.format_exc().replace('\n', self.delimiter)
            header = 'ERROR - Error processing cmd line: {line}'.format(line=line)
            err_msg = self.delimiter.join([header, err])
            self.sendLine(err_msg)
            return

        self.sendLine('OK')


class SystemControlFactory(Factory):

    def __init__(self, camera, images_server, vn):
        self.camera = camera
        self.images_server = images_server
        self.imu = vn

    def buildProtocol(self, addr):
        return SystemControlProtocol(self, addr)


class NewImagesQueue(object):
    def __init__(self, images_server, use_timestamp=False):
        self.images_server = images_server
        self.use_timestamp = use_timestamp

    def _watchThread(self):
        while True:
            obj = self.queue.get(True, None)

            if obj is None:
                return

            if self.use_timestamp:
                path = obj[0]
                time = obj[1] if len(obj) > 1 else datetime.now()
            else:
                path = obj
                time = datetime.now()

            self.onChange(path, time)

    def start(self):
        self.queue = Queue(0)
        deferToThread(self._watchThread)

    def stop(self):
        self.queue.put(None, False)

    def onChange(self, path, time):
        log.msg('Identified new image {img} at timestamp {time}'.format(img=path, time=time))

        deferToThread(self.images_server.handleNewImage, path, time)


class FlightDataSender(object):
    def __init__(self, images_server):
        self.images_server = images_server
        self.queue = None

    def _sendThread(self):
        while True:
            try:
                self.queue.get(True, 0.5)
                return
            except:
                pass

            self.images_server.sendFlightData()

    def start(self):
        self.queue = Queue(0)
        deferToThread(self._sendThread)

    def stop(self):
        self.queue.put(None, False)


def deferToThread(f, *args, **kwargs):
    #threads.deferToThread(f, *args, **kwargs)
    threads.deferToThreadPool(reactor, thread_pool, f, *args, **kwargs)


def shutdown_server(camera, fds, fs, vn):
    """Shutdown the server in a clean manner."""

    camera.stopShooting()
    fds.stop()
    fs.stop()

    if vn is not None:
        vn.close()

    global thread_pool
    thread_pool.stop()


def start_server(
    camera_type,
    simulate_pixhawk,
    simulate_targets,
    camera_ctl_port=gs.CAMERA_CTL_PORT,
    zmq_camera_notice_port=gs.ZMQ_CAMERA_NOTICE_PORT,
    zmq_camera_files_port=gs.ZMQ_CAMERA_FILES_PORT):
    """
    Start the airborne server.

    Parameters
    ----------
    camera_type: string
        Camera type. Options: [canon (default), simlulation, android].
    camera_ctl_port: int, optional(=8000)
        Port used by server.
    """

    global thread_pool
    thread_pool = ThreadPool(minthreads=MINTHREADS, maxthreads=MAXTHREADS)
    thread_pool.start()

    #
    # Create the auvsi data folder.
    #
    if not os.path.exists(gs.AUVSI_BASE_FOLDER):
        os.makedirs(gs.AUVSI_BASE_FOLDER)

    #
    # Setup logging.
    #
    log.startLogging(stdout)
    log.addObserver(
        log.FileLogObserver(
            file(os.path.join(gs.AUVSI_BASE_FOLDER, 'server.log'), 'a+')
            ).emit
    )

    #
    # Initialize the imageprocessing module.
    #
    IM.initIM()

    #
    # Initialize the pixhawk module.
    #
    if not simulate_pixhawk:
        PH.initPixHawk()
    else:
        PH.initPixHawkSimulation()

    try:
        vn = VectorNav.create()
        vn.open(VectorNav.MODE_ASYNC)
    except:
        log.msg('WARNING: Could not find VectorNav')
        vn = None

    #
    # Setup the Images server.
    #
    images_server = ImagesServer(
        zmq_camera_notice_port,
        zmq_camera_files_port,
        vn
    )

    #
    # add a watcher on the images folder
    #
    fs = NewImagesQueue(images_server, use_timestamp=True)
    fs.start()

    fds = FlightDataSender(images_server)
    fds.start()

    #
    # Create the camera object.
    #
    if camera_type.lower() == 'canon':
        camera = CanonCamera()
    elif camera_type.lower() == 'simulation':
        camera = SimulationCamera(simulate_targets, fs.queue)
    elif camera_type.lower() == 'android':
        camera = AndroidCamera.createDefault(gs.IMAGES_FOLDER, fs.queue)
    elif camera_type.lower() == 'ptp':
        from AUVSIairborne.ptpcam import PTPCamera

        camera = PTPCamera.createDefault(gs.IMAGES_FOLDER, fs.queue)
    else:
        raise NotImplementedError('Camera type {camera}, not supported.'.format(camera=camera_type))

    #
    # Startup the reactor.
    #
    control_factory = SystemControlFactory(camera, images_server, vn)
    reactor.listenTCP(camera_ctl_port, control_factory)
    reactor.addSystemEventTrigger('before', 'shutdown', shutdown_server, camera=camera, fds=fds, fs=fs, vn=vn)
    reactor.run()
