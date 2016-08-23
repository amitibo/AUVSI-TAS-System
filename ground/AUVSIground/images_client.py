from twisted.python import log
import global_settings as gs
import zmq
from txzmq import ZmqEndpoint, ZmqFactory, ZmqPushConnection, ZmqPullConnection
from txzmq import ZmqPubConnection, ZmqSubConnection, ZmqREQConnection, ZmqREPConnection
import traceback
import json
import os


#
# This a bug fix to the txzmq that enables publishing multipart messages.
#
class MyZmqPubConnection(ZmqPubConnection):
    """
    Publishing in broadcast manner.
    """

    def publish(self, message, tag=b''):
        """
        Publish `message` with specified `tag`.

        :param message: message data
        :type message: str
        :param tag: message tag
        :type tag: str
        """
        if type(message) == str:
            self.send(tag + b'\0' + message)
        else:
            self.send([tag] + message)


class MyZmqSubConnection(ZmqSubConnection):
    """
    Subscribing to messages published by publishers.

    Subclass this class and implement :meth:`gotMessage` to handle incoming
    messages.
    """
    def messageReceived(self, message):
        """
        Overridden from :class:`ZmqConnection` to process
        and unframe incoming messages.

        All parsed messages are passed to :meth:`gotMessage`.

        :param message: message data
        """
        if len(message) > 1:
            # compatibility receiving of tag as first part
            # of multi-part message
            self.gotMessage(message[1:], message[0])
        else:
            self.gotMessage(*reversed(message[0].split(b'\0', 1)))


class ControllerSyncConnection(ZmqREPConnection):
    def __init__(self, factory, endpoint, client):
        ZmqREPConnection.__init__(self, factory, endpoint=endpoint)
        self.client = client

    def gotMessage(self, messageId, *messageParts):
        rep = None
        try:
            log.msg("Handling sync request")
            rep = self.client.handleSyncRequest(messageParts)
        except Exception as e:
            log.err(e, "Error handling sync request")

        if rep is None:
            rep = [ 'err' ]

        self.reply(messageId, *rep)


class ImagesClient(object):
    """Handle the image/crops transfer from the airborne server."""

    def __init__(self, app, ip_camera, role, ip_controller):

        if role == gs.CONTROLLER:
            self.images_folder = gs.CTRL_IMAGES_FOLDER
            self.crops_folder = gs.CTRL_CROPS_FOLDER
            self.flightdata_folder = gs.CTRL_FLIGHTDATA_FOLDER
            self.thumbs_folder = None
        else:
            self.images_folder = gs.IMAGES_FOLDER
            self.crops_folder = gs.CROPS_FOLDER
            self.flightdata_folder = gs.FLIGHTDATA_FOLDER
            self.thumbs_folder = gs.THUMBNAILS_FOLDER

        if not os.path.exists(self.images_folder):
            os.makedirs(self.images_folder)
        if not os.path.exists(self.crops_folder):
            os.makedirs(self.crops_folder)
        if not os.path.exists(self.flightdata_folder):
            os.makedirs(self.flightdata_folder)
        if self.thumbs_folder is not None and not os.path.exists(self.thumbs_folder):
            os.makedirs(self.thumbs_folder)

        self.role = role

        #
        # Setup the zmq socket used for receiving images.
        #
        self.zmq_factory = ZmqFactory()
        if self.role == gs.CONTROLLER:
            #
            # Socket for pulling notices about images from the camera.
            #
            endpoint = ZmqEndpoint('connect', 'tcp://{server_ip}:{zmq_port}'.format(server_ip=ip_camera, zmq_port=gs.ZMQ_CAMERA_NOTICE_PORT))
            self.pull_socket = ZmqPullConnection(self.zmq_factory, endpoint)
            self.pull_socket.onPull = self.handlePullMessage

            #
            # Socket for requesting images from the camera.
            #
            endpoint = ZmqEndpoint('connect', 'tcp://{server_ip}:{zmq_port}'.format(server_ip=ip_camera, zmq_port=gs.ZMQ_CAMERA_FILES_PORT))
            self.req_socket = ZmqREQConnection(self.zmq_factory, endpoint)

            #
            # Socket for publishing images to subscribers.
            #
            endpoint = ZmqEndpoint('bind', 'tcp://0.0.0.0:{zmq_port}'.format(zmq_port=gs.ZMQ_PRIMARY_GS_PORT))
            self.pub_socket = MyZmqPubConnection(self.zmq_factory, endpoint)

            #
            # Socket for responding with queued images or sync data.
            #
            endpoint = ZmqEndpoint('bind', 'tcp://*:{zmq_port}'.format(zmq_port=gs.ZMQ_PRIMARY_GS_CONTROLLER_PORT))
            self.sync_rep_socket = ControllerSyncConnection(self.zmq_factory, endpoint, self)

        else:
            #
            # Socket for subscribing to images.
            #
            endpoint = ZmqEndpoint('connect', 'tcp://{server_ip}:{zmq_port}'.format(server_ip=ip_controller, zmq_port=gs.ZMQ_PRIMARY_GS_PORT))
            self.sub_socket = MyZmqSubConnection(self.zmq_factory, endpoint)
            self.sub_socket.subscribe(gs.SUB_TAG)
            self.sub_socket.gotMessage = self.handleNewMessage

            #
            # Socket for requesting queued images or sync data from the controller.
            #
            endpoint = ZmqEndpoint('connect', 'tcp://{server_ip}:{zmq_port}'.format(server_ip=ip_controller, zmq_port=gs.ZMQ_PRIMARY_GS_CONTROLLER_PORT))
            self.sync_req_socket = ZmqREQConnection(self.zmq_factory, endpoint)

            log.msg('Sending sync request')
            self.requestSyncImageList()
            self.requestSyncCropList()

        self.app = app

    def shutdown(self):
        """Shutdown the zmq connection."""

        self.zmq_factory.shutdown()

    def handlePullMessage(self, new_pull_message, ignore_tag=None):
        """Handle a notice from the camera about a new image."""

        try:
            if self.role != gs.CONTROLLER:
                return

            data_type = new_pull_message[0]

            if data_type == gs.RESIZED_IMAGE:
                image_name = new_pull_message[1]
                log.msg("Got new pull message: {id}".format(id=image_name))

                #
                # Request the new image.
                #
                self.req_socket.sendMsg(image_name).addCallback(self.handleNewMessage)
            else:
                #
                # Handle other messages normally.
                #
                self.handleNewMessage(new_pull_message, ignore_tag)
        except Exception as e:
            log.err(e, 'handlePullMessage')

    def handleNewMessage(self, new_data_message, ignore_tag=None):
        """Analyze the data received from the airborne server."""

        try:
            if self.role == gs.CONTROLLER:
                self.pub_socket.publish(new_data_message, tag=gs.SUB_TAG)

            data_type = new_data_message[0]

            if data_type == gs.RESIZED_IMAGE:
                self.handleNewImg(new_data_message[1:])
            elif data_type in (gs.MANUAL_CROP, gs.AUTO_CROP):
                self.handleNewCrop(data_type, new_data_message[1:])
            elif data_type == gs.FLIGHT_DATA:
                self.handleNewFlightData(new_data_message[1:])
                #log.msg("Got updated flight data")
            elif data_type == gs.AUTO_ANALYSIS:
                self.handleNewADLCresults(new_data_message[1:])
            elif data_type == gs.STATE:
                self.handleState(new_data_message[1:])
            elif data_type == gs.TARGET_INFO:
                self.handleNewTarget(new_data_message[1:])
            else:
                log.msg("Unkown data type received from image server: {data_type}".format(data_type=data_type))
        except Exception as e:
            log.err(traceback.format_exc(), 'handleNewMessage')

    def handleNewImg(self, new_img_message):
        """Should be implemented by a subclass"""

        pass

    def handleNewCrop(self, crop_type, new_crop_message):
        """Should be implemented by a subclass"""

        pass

    def handleNewFlightData(self, new_fd_message):
        """Should be implemented by a subclass"""

        pass

    def handleNewTarget(self, new_target_message):
        """Should be implemented by a subclass"""

        pass

    def handleNewADLCresults(self, new_target_message):
        """Should be implemented by a subclass"""

        pass

    def handleSyncImageListRequest(self, message):
        """Should be implemented by a controller subclass"""
        """Should return response message"""
        pass

    def handleSyncCropListRequest(self, message):
        """Should be implemented by a controller subclass"""
        """Should return response message"""
        pass

    def handleSyncQueueRequest(self, message):
        """Should be implemented by a controller subclass"""
        """Should return response message"""
        pass

    def handleSyncImageRequest(self, message):
        """Should be implemented by a controller subclass"""
        """Should return response message"""
        pass

    def handleSyncCropRequest(self, message):
        """Should be implemented by a controller subclass"""
        """Should return response message"""
        pass

    def handleSyncTargetRequest(self, message):
        self.pub_socket.publish([gs.TARGET_INFO]+list(message), tag=gs.SUB_TAG)
        self.handleNewTarget(message)
        return []

    def handleSyncRequest(self, message):
        cmd = message[0]
        rep = None

        if cmd == gs.SYNC_LIST:
            sync_type = message[1]

            if sync_type == gs.SYNC_LIST_IMAGES:
                rep = self.handleSyncImageListRequest()
            elif sync_type == gs.SYNC_LIST_CROPS:
                rep = self.handleSyncCropListRequest()
            else:
                log.msg('Unknown sync list request: {type}'.format(type=sync_type))

            if rep is not None:
                rep = rep[:]
                rep.insert(0, sync_type)

        elif cmd == gs.SYNC_QUEUE:
            rep = self.handleSyncQueueRequest()
        elif cmd == gs.SYNC_IMAGE:
            rep = self.handleSyncImageRequest(message[1:])
        elif cmd == gs.SYNC_CROP:
            rep = self.handleSyncCropRequest(message[1:])
        elif cmd == gs.SYNC_TARGET:
            rep = self.handleSyncTargetRequest(message[1:])

        if rep is not None:
            rep = rep[:]
            rep.insert(0, cmd)

        return rep

    def handleSyncImageListResponse(self, message):
        """Should be implemented by a primary/secondary subclass"""
        pass

    def handleSyncCropListResponse(self, message):
        """Should be implemented by a primary/secondary subclass"""
        pass

    def handleSyncImageResponse(self, message):
        """Should be implemented by a primary/secondary subclass"""
        pass

    def handleSyncCropResponse(self, message):
        """Should be implemented by a primary/secondary subclass"""
        pass

    def handleSyncQueueResponse(self, message):
        """Should be implemented by a primary/secondary subclass"""
        pass

    def handleSyncTargetResponse(self, message):
        pass

    def handleSyncResponse(self, message):
        if self.role == gs.CONTROLLER:
            return

        cmd = message[0]

        if cmd == gs.SYNC_LIST:
            if message[1] == gs.SYNC_LIST_IMAGES:
                self.handleSyncImageListResponse(message[2:])
            elif message[1] == gs.SYNC_LIST_CROPS:
                self.handleSyncCropListResponse(message[2:])
            else:
                log.msg('Unknown sync list response: {type}'.format(type=message[1]))
        elif cmd == gs.SYNC_QUEUE:
            self.handleSyncQueueResponse(message[1:])
        elif cmd == gs.SYNC_IMAGE:
            self.handleSyncImageResponse(message[1:])
        elif cmd == gs.SYNC_CROP:
            self.handleSyncCropResponse(message[1:])
        elif cmd == gs.SYNC_TARGET:
            self.handleSyncTargetResponse(message[1:])
        else:
            log.msg('Unknown sync response: {cmd}'.format(cmd=cmd))

    def requestSyncMsg(self, *msg):
        if self.role != gs.CONTROLLER:
            self.sync_req_socket.sendMsg(*msg).addCallback(self.handleSyncResponse)

    def requestSyncImageList(self):
        self.requestSyncMsg(gs.SYNC_LIST, gs.SYNC_LIST_IMAGES)

    def requestSyncCropList(self):
        self.requestSyncMsg(gs.SYNC_LIST, gs.SYNC_LIST_CROPS)

    def requestSyncImage(self, image_name):
        self.requestSyncMsg(gs.SYNC_IMAGE, image_name)

    def requestSyncCrop(self, crop_name):
        self.requestSyncMsg(gs.SYNC_CROP, crop_name)

    def requestSyncQueue(self):
        self.requestSyncMsg(gs.SYNC_QUEUE)

    def notifyTargetManual(self, crop_name, crop_yaw, lat, lon, target_type, shape, shape_color, text, text_color, orientation_text, desc):
        self.requestSyncMsg(gs.SYNC_TARGET, gs.TARGET_MANUAL, crop_name, str(crop_yaw), target_type, str(lat), str(lon), shape, shape_color, text, text_color, orientation_text)

    def notifyTargetAuto(self, target_id, crop_name, crop_yaw, lat, lon, target_type, shape, shape_color, text, text_color, orientation_text):
        self.requestSyncMsg(gs.SYNC_TARGET, gs.TARGET_AUTO, target_id, crop_name, str(crop_yaw), target_type, str(lat), str(lon), shape, shape_color, text, text_color, orientation_text)

    def handleState(self, message):
        type = message[0]

        if type == gs.STATE_DOWNLOAD:
            self.handleDownloadState(message[1:])
        elif type == gs.STATE_SHOOT:
            self.handleCameraState(message[1:])

    def handleDownloadState(self, message):
        pass

    def handleCameraState(self, message):
        pass

class AutoClient(object):
    """Handle the communication with the automatic detection servers."""

    def __init__(self, app):

        #
        # Setup the zmq socket used for receiving images.
        #
        self.zmq_factory = ZmqFactory()

        #
        # Socket for pushing images and crops to the automatic processing servers.
        #
        endpoint = ZmqEndpoint('bind', 'tcp://*:{zmq_port}'.format(zmq_port=gs.ZMQ_AUTO_WORKER_PUSH))
        self.push_socket = ZmqPushConnection(self.zmq_factory, endpoint)

        #
        # Socket for pulling results from the automatic processing servers.
        #
        endpoint = ZmqEndpoint('bind', 'tcp://*:{zmq_port}'.format(zmq_port=gs.ZMQ_AUTO_WORKER_PULL))
        self.pull_socket = ZmqPullConnection(self.zmq_factory, endpoint)
        self.pull_socket.onPull = self.handleNewMessage

        self.app = app

    def shutdown(self):
        """Shutdown the zmq connection."""

        self.zmq_factory.shutdown()

    def sendNewImage(self, img_path, data_path):
        """Send a new image (got from the primary ip) to the auto server"""

        data = [gs.RESIZED_IMAGE, img_path, data_path]

        try:
            log.msg("Sending of img {img}.".format(img=img_path))
            self.push_socket.push(data)
        except zmq.error.Again:
            log.msg("Skipping sending of {img}, no pull consumers...".format(img=img_path))

    def sendNewCrop(self, crop_path, yaw, lat, lon):
        """Send a new (auto) crop from the primary ip to the auto server."""

        data = [gs.AUTO_CROP, crop_path, yaw, lat, lon]

        try:
            log.msg("Sending of crop {crop}.".format(crop=crop_path))
            self.push_socket.push(data)
        except zmq.error.Again:
            log.msg("Skipping sending of crop {crop}, no pull consumers...".format(crop=crop_path))

    def handleNewMessage(self, new_data_message, ignore_tag=None):
        """Analyze the data received from the auto server."""

        try:
            data_type = new_data_message[0]

            if data_type == gs.CROP_REQUESTS:
                img_path, requested_crops = new_data_message[1], json.loads(new_data_message[2])

                if len(requested_crops) == 0:
                    log.msg(
                        'No target candidates found for image {img_name}'.format(img_name=os.path.split(img_path)[-1])
                    )
                    return

                self.app.downloadCrops(img_path, requested_crops)

            elif data_type == gs.TARGET_DATA:
                crop_path, target_details = new_data_message[1], json.loads(new_data_message[2])

                if target_details is {}:
                    log.msg(
                        'Crop {crop_name} not a target'.format(crop_name=os.path.split(crop_path)[-1])
                    )
                    return

                self.app.newTarget(crop_path, target_details)
            else:
                log.msg("Unkown data type received from auto server: {data_type}".format(data_type=data_type))
        except Exception as e:
            log.err(e, 'handleNewMessage')

class AutoServer(object):
    """Handle the communication of the automatic detection servers."""

    def __init__(self, worker):

        log.msg("Initializing auto server")

        #
        # Setup the zmq socket used for receiving images.
        #
        self.zmq_factory = ZmqFactory()

        #
        # Socket for pulling images and crops from the automatic client.
        #
        endpoint = ZmqEndpoint('connect', 'tcp://localhost:{zmq_port}'.format(zmq_port=gs.ZMQ_AUTO_WORKER_PUSH))
        self.pull_socket = ZmqPullConnection(self.zmq_factory, endpoint)
        self.pull_socket.onPull = self.handleNewMessage

        #
        # Socket for pushing results to the automatic client.
        #
        endpoint = ZmqEndpoint('connect', 'tcp://localhost:{zmq_port}'.format(zmq_port=gs.ZMQ_AUTO_WORKER_PULL))
        self.push_socket = ZmqPushConnection(self.zmq_factory, endpoint)

        self.worker = worker

    def shutdown(self):
        """Shutdown the zmq connection."""

        self.zmq_factory.shutdown()

    def requestCrops(self, img_path, crops):
        """Send a request from a worker to the auto client for crops."""

        data = [gs.CROP_REQUESTS, img_path, json.dumps(crops)]

        try:
            log.msg("Sending crop requests for img {img}: {crops}.".format(img=img_path, crops=crops))
            self.push_socket.push(data)
        except zmq.error.Again:
            log.msg("Failed sending crops request")

    def sendTarget(self, crop_path, target_details):
        """Send the details of a target (from a worker to the auto client)."""

        data = [gs.TARGET_DATA, crop_path, json.dumps(target_details)]

        try:
            log.msg("Sending of target in {crop}, with {data}.".format(crop=crop_path, data=data))
            self.push_socket.push(data)
        except zmq.error.Again:
            log.msg("Skipping sending of crop {crop}, no pull consumers...".format(crop=crop_path))

    def handleNewMessage(self, new_data_message, ignore_tag=None):
        """Analyze the data received from the auto client."""

        try:
            data_type = new_data_message[0]

            if data_type == gs.RESIZED_IMAGE:
                img_path, data_path = new_data_message[1:]

                crops = self.worker.processNewImage(img_path, data_path)
                self.requestCrops(img_path, crops)

            elif data_type == gs.AUTO_CROP:
                crop_path, yaw, lat, lon = new_data_message[1:]
                yaw = float(yaw)
                lat = float(lat)
                lon = float(lon)

                target_details = self.worker.processNewCrop(crop_path, yaw, lat, lon)
                self.sendTarget(crop_path, target_details)
            else:
                log.msg("Unkown data type received from auto server: {data_type}".format(data_type=data_type))
        except Exception as e:
            log.err(e, 'handleNewMessage')
