from __future__ import division
#install_twisted_rector must be called before importing the reactor
from kivy.support import install_twisted_reactor
install_twisted_reactor()

import server

from twisted.python import log
from twisted.web.server import Site
from twisted.web.resource import Resource
from twisted.internet import reactor

from kivy.app import App
from kivy.uix.settings import SettingsWithTabbedPanel
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.button import Button
from kivy.storage.jsonstore import JsonStore

from AUVSIground.widgets import *
from AUVSIground.images_client import ImagesClient

import AUVSIcv

import pkg_resources
import global_settings as gs
import numpy as np
from random import random
from math import sqrt
from sys import stdout
import glob
import json
import os
from scipy import ndimage
#from Queue import Queue

from settingsjson import network_json, version_json

flight_data = None


class MyImagesClient(ImagesClient):
    """Handle the image/crops transfer from the airborne server."""

    def __init__(self, app, ip_camera, role, ip_controller):
        super(MyImagesClient, self).__init__(app, ip_camera, role, ip_controller)

        self._images = []
        self._crops = []
        self._queues = []

        for i in range(gs.IMAGE_QUEUE_COUNT):
            self._queues.append([])

        self._store = JsonStore(os.path.join(gs.AUVSI_BASE_FOLDER, 'controller.json'))
        self._loadState()

    def _loadState(self):

        img_paths = sorted(glob.glob(os.path.join(gs.CTRL_IMAGES_FOLDER, '*.jpg')))
        self._images = [os.path.split(path)[1] for path in img_paths]

        crop_paths = sorted(glob.glob(os.path.join(gs.CTRL_CROPS_FOLDER, 'manual_*.jpg')))
        self._crops = [os.path.split(path)[1] for path in crop_paths]

        if self._store.exists('queues'):
            queues = self._store.get('queues')['items']
            self._queues = []

            for i in range(len(queues)):
                self._queues.append([ str(item) for item in queues[i] ])


    def _saveState(self):
        self._store.put('queues', items=self._queues)

    def _loadImage(self, image_name):
        data_name = os.path.splitext(image_name)[0] + '.json'
        img_path = os.path.join(self.images_folder, image_name)
        data_path = os.path.join(self.flightdata_folder, data_name)

        with open(img_path, 'rb') as f:
            img_data = f.read()

        with open(data_path, 'rb') as f:
            flight_data = f.read()

        return img_data, flight_data

    def _loadCrop(self, crop_name):
        data_name = os.path.splitext(crop_name)[0] + '.json'
        crop_path = os.path.join(self.crops_folder, crop_name)
        data_path = os.path.join(self.flightdata_folder, data_name)

        with open(crop_path, 'rb') as f:
            crop_data = f.read()

        with open(data_path, 'rb') as f:
            flight_data = json.load(f)

        d = {
            'name': crop_name,
            'data': crop_data,
            'yaw': flight_data['yaw'],
            'lat': flight_data['lat'],
            'lon': flight_data['lon'],
            'orig_img': flight_data['orig_img'],
            'coords': flight_data['coords']
        }

        return d

    def handleSyncImageListRequest(self):
        return self._images

    def handleSyncCropListRequest(self):
        return self._crops

    def handleSyncQueueRequest(self):
        i = 1
        for queue in self._queues:
            if len(queue) > 0:
                item = [ queue.pop(0), str(i) ]
                self._saveState()
                return item

            i += 1
        return None

    def handleSyncImageRequest(self, message):
        image_name = message[0]
        data = self._loadImage(image_name)

        if data is not None and len(data) > 0:
            return [ image_name, data[0], data[1] ]

        return None

    def handleSyncCropRequest(self, message):
        crop_name = message[0]
        data = self._loadCrop(crop_name)

        if data is not None:
            return [
                str(data['orig_img']),
                str(data['coords'][0]),
                str(data['coords'][1]),
                str(data['coords'][2]),
                str(data['coords'][3]),
                str(data['yaw']),
                str(data['lat']),
                str(data['lon']),
                crop_name,
                data['data']
            ]

        return None

    def handleNewImg(self, new_img_message):
        """Handle the new image zmq message."""

        img_name, img_data, flight_data = new_img_message
        self._images.append(img_name)

        for queue in self._queues:
            queue.append(img_name)

        self._saveState()
        flight_data = json.loads(flight_data)

        #
        # Set paths
        #
        new_data = os.path.splitext(img_name)[0]+'.json'
        img_path = os.path.join(self.images_folder, img_name)
        data_path = os.path.join(self.flightdata_folder, new_data)

        #
        # Save flight data
        #
        with open(data_path, 'wb') as f:
            json.dump(flight_data, f)

        #
        # Save image
        #
        with open(img_path, 'wb') as f:
            f.write(img_data)
        log.msg('Finished Downloading image {new_img}'.format(new_img=img_name))

    def handleNewCrop(self, crop_type, new_crop_message):
        """Handle the new crop zmq message."""

        #
        # The gui handles only manual crops (the auto crops are
        # sent to the auto secondary)
        #
        #if crop_type != gs.MANUAL_CROP:
        #    log.msg('None manual crop ignored by primary.')
        #    return
        is_auto = crop_type != gs.MANUAL_CROP

        #
        # coords are ignored in the case of manual crops.
        #
        orig_img = new_crop_message[0]
        coords = new_crop_message[1:5]
        yaw, lat, lon, crop_name, crop_data = new_crop_message[5:]
        self._crops.append(crop_name)

        yaw = float(yaw)
        lat = float(lat)
        lon = float(lon)

        #
        # Calculate paths
        #
        crop_path = os.path.join(self.crops_folder, crop_name)

        #
        # Save crop
        #
        with open(crop_path, 'wb') as f:
            f.write(crop_data)

        log.msg('Finished Downloading crop {crop_path}'.format(crop_path=crop_path))

        data_name = os.path.splitext(crop_name)[0]+'.json'
        data_path = os.path.join(self.flightdata_folder, data_name)
        crop_details = {'yaw':yaw, 'lat':lat, 'lon':lon, 'orig_img':orig_img, 'coords':coords, 'auto':is_auto}
        with open(data_path, 'wb') as f:
            json.dump(crop_details, f)

    def handleNewFlightData(self, new_fd_message):
        global flight_data

        try:
            flight_data = json.loads(new_fd_message[0])
        except:
            log.msg('Error parsing flight data')


class ControllerApp(App):
    """Main AUVSI ground system application."""

    kv_directory = pkg_resources.resource_filename('AUVSIground', 'resources')
    connection = None
    title = 'Ground Controller GUI'
    icon = pkg_resources.resource_filename('AUVSIground', 'resources/tyto_icon.png')

    def build(self):
        """Main build function of the Kivy application."""

        #
        # Setup logging.
        #
        if not os.path.exists(gs.AUVSI_BASE_FOLDER):
            os.makedirs(gs.AUVSI_BASE_FOLDER)

        log.startLogging(stdout)
        log.addObserver(
            log.FileLogObserver(
                file(os.path.join(gs.AUVSI_BASE_FOLDER, 'controller.log'), 'a+')
                ).emit
        )

        self.settings_cls = SettingsWithTabbedPanel

        #
        # Start up the local server.
        #
        self.connect_to_server()

        #
        # Load previously saved data
        #
        self.populateGalleryLists()

        #start_fd_server();

    def populateGalleryLists(self):
        """Populate the images list that were already downloaded."""

        #
        # Scan the images folder and load all images to the gallery
        #
        img_paths = sorted(glob.glob(os.path.join(gs.CTRL_IMAGES_FOLDER, '*.jpg')))
        img_names = [os.path.splitext(os.path.split(path)[1])[0] for path in img_paths]
        data_paths = [os.path.join(gs.FLIGHTDATA_FOLDER, name+'.json') for name in img_names]
        #img_tn_paths = [os.path.join(gs.THUMBNAILS_FOLDER, name+'_tn.jpg') for name in img_names]
        #img_tn_pressed_paths = [os.path.join(gs.THUMBNAILS_FOLDER, name+'_pressed_tn.jpg') for name in img_names]

        #for img_path, img_tn_path, img_tn_pressed_path, data_path in zip(img_paths, img_tn_paths, img_tn_pressed_paths, data_paths):
        #    self._populateImagesList(img_path, img_tn_path, img_tn_pressed_path, data_path)

        #
        # Scan the crops folder and load all crops to the gallery
        #
        crop_paths = sorted(glob.glob(os.path.join(gs.CTRL_CROPS_FOLDER, 'manual_*.jpg')))
        crop_names = [os.path.splitext(os.path.split(path)[1])[0] for path in crop_paths]
        data_paths = [os.path.join(gs.FLIGHTDATA_FOLDER, name+'.json') for name in crop_names]
        #crop_tn_paths = [os.path.join(gs.THUMBNAILS_FOLDER, name+'_tn.jpg') for name in crop_names]

        #for crop_path, crop_tn_path, data_path in zip(crop_paths, crop_tn_paths, data_paths):
        #    with open(data_path, 'rb') as f:
        #        crop_data = json.load(f)
        #
        #    self._populateCropsList(crop_path, crop_tn_path, crop_data['yaw'], crop_data['lat'], crop_data['lon'])

    def build_config(self, config):
        """Create the default config (used the first time the application is run)"""

        config.setdefaults(
            'Network', {'IP': '192.168.1.101', 'role': gs.CONTROLLER, 'IP_CONTROLLER': '192.168.1.201'}
            )

        #
        # Disable multi touch emulation with the mouse.
        #
        from kivy.config import Config
        Config.set('input', 'mouse', 'mouse,disable_multitouch')

    def build_settings(self, settings):
        """Build the settings menu."""

        settings.add_json_panel("Network", self.config, data=network_json)
        settings.add_json_panel("Version", self.config, data=version_json)

    def on_config_change(self, config, section, key, value):
        """Handle change in the settings."""

        if section == 'Network':
            self.connect_to_server()

    def connect_to_server(self):
        """Initiate connection to airborne server."""

        server.setserver(
            ip=self.config.get('Network', 'ip'),
            role=gs.CONTROLLER,
            ip_controller=self.config.get('Network', 'ip_controller'),
        )
        self.server = server.connect(self, MyImagesClient)

    def on_connection(self):
        """Callback on successful connection to the server."""

        self.root.connect_label.canvas.before.children[0].rgb = (0, 0, 1)
        self.root.connect_label.text = 'Connected'

    def on_disconnection(self):
        """Callback on disconnection from the server."""

        self.root.connect_label.canvas.before.children[0].rgb = (1, 0, 0)
        self.root.connect_label.text = 'Disconnected'

    def log_message(self, msg):
        """"""

        log.msg(msg)

def start_fd_server():
    root = Resource()
    mavlink = Resource()
    root.putChild('mavlink', mavlink)
    mavlink.putChild('', FlightDataView())
    factory = Site(root)

    reactor.listenTCP(56781, factory)

class FlightDataView(Resource):
    def render_GET(self, request):
        global flight_data

        fd = flight_data
        j = {}

        if fd is not None:
            lat = fd.get('lat', 0) * 1e-7
            lon = fd.get('lon', 0) * 1e-7
            alt = fd.get('relative_alt', 0) * 1e-3

            j['GPS_RAW_INT'] = {
                'msg': {
                    'lat': int(lat * 10000000),
                    'lon': int(lon * 10000000),
                    'alt': int(alt * 1000)
                },
                'index': 0,
                'time_usec': 0
            }

        return json.dumps(j)

    def render_POST(self, request):
        return render_GET(request)

if __name__ == '__main__':
    ControllerApp().run()
