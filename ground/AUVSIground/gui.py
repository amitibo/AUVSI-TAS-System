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

from .widgets import *
from .images_client import ImagesClient

import AUVSIcv

import pkg_resources
import global_settings as gs
import numpy as np
from random import random
from math import sqrt
from sys import stdout
import glob
import json
import cv2
import os
from scipy import ndimage
from collections import OrderedDict

import ftplib
from time import sleep
from socket import timeout, error

from settingsjson import network_json, camera_json, cv_json, admin_json, imu_json, version_json

flight_data = None


class MyImagesClient(ImagesClient):
    """Handle the image/crops transfer from the airborne server."""

    def __init__(self, app, ip_camera, role, ip_controller):
        super(MyImagesClient, self).__init__(app, ip_camera, role, ip_controller)

        self._images = []
        self._crops = []

    def addExistingImg(self, img_name):
        self._images.append(img_name)

    def handleNewImg(self, new_img_message):
        """Handle the new image zmq message."""

        img_name, img_data, flight_data = new_img_message
        flight_data = json.loads(flight_data)

        #
        # Set paths
        #
        new_data = os.path.splitext(img_name)[0]+'.json'
        img_path = os.path.join(self.images_folder, img_name)
        data_path = os.path.join(self.flightdata_folder, new_data)
        new_img_tn = '{}_tn{}'.format(*os.path.splitext(img_name))
        img_tn_path = os.path.join(self.thumbs_folder, new_img_tn)
        new_img_tn_pressed = '{}_pressed_tn{}'.format(*os.path.splitext(img_name))
        img_tn_pressed_path = os.path.join(self.thumbs_folder, new_img_tn_pressed)

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

        #
        # Resize a thumbnail.
        #
        img = cv2.imread(img_path)
        r = 100.0 / img.shape[1]
        dim = (100, int(img.shape[0] * r))
        img_tn = cv2.resize(img, dim, interpolation=cv2.INTER_AREA)
        img_tn_pressed = img_tn.copy()
        img_tn_pressed[..., 1:] = 127
        cv2.imwrite(img_tn_path, img_tn)
        cv2.imwrite(img_tn_pressed_path, img_tn_pressed)

        #
        # Add the new image to the GUI
        #
        self.app._populateImagesList(
            img_name=img_name,
            img_path=img_path,
            img_tn_path=img_tn_path,
            img_tn_pressed_path=img_tn_pressed_path,
            data_path=data_path
        )

        self._images.append(img_name)
        self.app.checkRequestQueueImage()

    def handleSyncImageResponse(self, message):
        log.msg('Got missing image: {img_name}'.format(img_name=message[0]))
        self.handleNewImg(message)

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
        yaw, lat, lon, crop_name, crop_data = new_crop_message[5:]
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

        log.msg('Finished Downloading crop {crop_path} ({type})'.format(crop_path=crop_path, type='automatic' if is_auto else 'manual'))

        #
        # Resize a thumbnail.
        #
        new_crop_tn = '{}_tn{}'.format(*os.path.splitext(crop_name))
        crop_tn_path = os.path.join(self.thumbs_folder, new_crop_tn)

        crop = cv2.imread(crop_path)
        crop_tn = cv2.resize(crop, (100, 100), interpolation=cv2.INTER_AREA)
        cv2.imwrite(crop_tn_path, crop_tn)

        data_name = os.path.splitext(crop_name)[0]+'.json'
        data_path = os.path.join(self.flightdata_folder, data_name)
        crop_details = {'yaw':yaw, 'lat':lat, 'lon':lon, 'orig_img':orig_img, 'auto':is_auto}
        with open(data_path, 'wb') as f:
            json.dump(crop_details, f)

        if not is_auto:
            #
            # Add the new crop to the GUI
            #
            self.app._populateCropsList(
                crop_path=crop_path,
                crop_tn_path=crop_tn_path,
                yaw=yaw,
                lat=lat,
                lon=lon,
                orig_img=orig_img
                )

        self._crops.append(crop_name)

    def handleSyncCropResponse(self, message):
        log.msg('Got missing crop: {crop_name}'.format(crop_name=message[3]))
        self.handleNewCrop(gs.MANUAL_CROP, message)

    def handleNewFlightData(self, new_fd_message):
        global flight_data
        flight_data = json.loads(new_fd_message[0])


    def handleSyncImageListResponse(self, message):
        log.msg('Got sync image list response')
        sync_images = message
        missing_images = [img for img in sync_images if img not in self._images]
        log.msg('Requesting {img_count} missing images'.format(img_count=len(missing_images)))
        for img in missing_images:
            log.msg('Requesting image {img_name}...'.format(img_name=img))
            self.requestSyncImage(img)

    def handleSyncCropListResponse(self, message):
        log.msg('Got sync crop list response')
        sync_crops = message
        missing_crops = [crop for crop in sync_crops if crop not in self._crops]
        log.msg('Requesting {crop_count} missing crops'.format(crop_count=len(missing_crops)))
        for crop in missing_crops:
            log.msg('Requesting crop {crop_name}...'.format(crop_name=crop))
            self.requestSyncCrop(crop)

    def handleSyncQueueResponse(self, message):
        self.app.addImageToQueue(message[0], message[1])

    def handleDownloadState(self, message):
        self.app.setDownloadState(message[0] == gs.STATE_ON)

    def handleCameraState(self, message):
        self.app.setCameraState(message[0] == gs.STATE_ON)

class ImageInfo(object):
    def __init__(self, name, btn):
        self.name = name
        self.btn = btn
        self.queue_ids = []
        self.view_count = 0
        self.queue_index = -1
        self.processed = False


class GUIApp(App):
    """Main AUVSI ground system application."""

    kv_directory = pkg_resources.resource_filename('AUVSIground', 'resources')
    connection = None
    title = 'Image Processing GUI'
    icon = pkg_resources.resource_filename('AUVSIground', 'resources/tyto_icon.png')

    def build(self):
        """Main build function of the Kivy application."""

        self._updating_ui = False

        #
        # Setup logging.
        #
        if not os.path.exists(gs.AUVSI_BASE_FOLDER):
            os.makedirs(gs.AUVSI_BASE_FOLDER)

        log.startLogging(stdout)
        log.addObserver(
            log.FileLogObserver(
                file(os.path.join(gs.AUVSI_BASE_FOLDER, 'gui.log'), 'a+')
                ).emit
        )

        self.settings_cls = SettingsWithTabbedPanel
        self._store = JsonStore(os.path.join(gs.AUVSI_BASE_FOLDER, 'gui.json'))

        #
        # Start up the local server.
        #
        self.connect_to_server()

        #
        # Setup the images gallery.
        #
        self.images = OrderedDict()
        self.img_buttons = OrderedDict()
        self.img_queue = []
        self.current_img_name = None
        self.current_queue_index = -1
        self.original_img = None
        self.mission_cnt = 1
        self.newMission()

        #
        # Load previously saved data
        #
        self.populateGalleryLists()
        self._loadState()

        if self.config.get('Network', 'role') == gs.PRIMARY:
            #start_fd_server();
            pass


    def focusCurrentImage(self):
        if self.current_img_name is not None and self.current_img_name in self.img_buttons:
            btn = self.img_buttons[self.current_img_name]
            btn.trigger_action(duration=0)
            btn.state = 'down'
            #self.root.images_gallery.scroll_view.scroll_to(btn, False)

    def _loadState(self):
        if self._store.exists('queue'):
            queue = self._store.get('queue')
            self.img_queue = queue['items']

            processed = queue['processed']
            for img_name in processed:
                if img_name in self.images:
                    self.images[img_name].processed = True

        if self._store.exists('selection'):
            sel = self._store.get('selection')
            self.current_img_name = sel['img_name']
            self.current_queue_index = sel['queue_index']

        self.focusCurrentImage()

        queue_index = 0

        for img_name, queue_id in self.img_queue:
            if img_name in self.images:
                img = self.images[img_name]
                img.queue_index = queue_index
                img.queue_ids.append(queue_id)
                self.updateImageText(img)

            queue_index += 1

    def _saveState(self):
        processed = [ img_name for img_name in self.images if self.images[img_name].processed ]
        self._store.put('queue', items=self.img_queue, processed=processed)
        self._store.put('selection', img_name=self.current_img_name, queue_index=self.current_queue_index)

    def updateImageText(self, img):
        proc = '' if img.processed else '*'
        img.btn.text = u'[b][color=ff0000]{proc} {ids}[/color][/b]'.format(proc=proc, ids=', '.join(img.queue_ids))

    def addImageToQueue(self, img_name, queue_id):
        if not img_name in self.images:
            #server.getClient().requestSyncImage(img_name)
            return

        img = self.images[img_name]
        #img.btn.thumbnail = updated_thumbnail

        queue_index = len(self.img_queue)
        self.img_queue.append((img_name, queue_id))
        img.queue_index = queue_index
        img.queue_ids.append(queue_id)
        self.updateImageText(img)

        self._saveState()
        #if img.view_count < img.queue_count:
        #    img.view_count += 1
        #    self.pending_images -= 1

    def checkRequestQueueImage(self):
        queue_index = -1

        if self.current_img_name is not None:
            queue_index = self.images[self.current_img_name].queue_index

        if len(self.img_queue) < gs.IMAGE_QUEUE_LOOK_AHEAD or queue_index >= len(self.img_queue) - gs.IMAGE_QUEUE_LOOK_AHEAD:
            server.getClient().requestSyncQueue()

    def _populateImagesList(self, img_name, img_path, img_tn_path, img_tn_pressed_path, data_path):
        """Store new image paths in image list."""

        class Callback:
            def __init__(self, app, img, img_name, img_path, data_path):
                self._app = app
                self._img = img
                self._img_name = img_name
                self._img_path = img_path
                self._data_path = data_path
                self._img_obj = None

            def __call__(self, instance):
                self._app.root.images_gallery.scroll_view.scroll_to(self._img.btn)

                if not self._img_obj:
                    self._img_obj = AUVSIcv.Image(self._img_path, self._data_path, K=AUVSIcv.global_settings.resized_K)
                self._app.root.images_gallery.updateImage(self._img_obj)
                self._app.current_img_name = self._img_name

                if self._img.view_count < len(self._img.queue_ids):
                    self._img.view_count += 1

                if not self._img.processed:
                    print 'Setting processed=True:', self._img_name
                    self._img.processed = True
                    self._app.updateImageText(self._img)

                self._app._saveState()
                self._app.checkRequestQueueImage()

        btn = ToggleButton(
            size_hint=(None, None),
            size=(100, 75),
            background_normal=img_tn_path,
            background_down=img_tn_pressed_path,
            group='shots',
            text='',
            halign='right',
            valign='bottom',
            text_size=(100, 75),
            markup=True
        )

        img = ImageInfo(img_name, btn)
        self.img_buttons[img_name] = btn
        self.images[img_name] = img

        btn.bind(on_press=Callback(self, img, img_name, img_path, data_path))
        self.root.images_gallery.stacked_layout.add_widget(btn)

    def capture_keyboard(self):
        self.root.images_gallery.scatter_image.setup_keyboard()

    def _populateCropsList(self, crop_path, crop_tn_path, yaw, lat, lon, orig_img):
        """Store new crop paths in crops list."""

        def callback_factory(app, crop_path, crop_yaw, crop_lat, crop_lon, crop_orig_img):

            def callback(instance):
                self.root.crops_gallery.updateCrop(crop_path, crop_yaw)
                self.root.crops_gallery.updateTargetLocation(crop_lat, crop_lon)
                self.root.crops_gallery.updateQRText("Press to decode QR")
                app.setOriginalImage(crop_orig_img)

            return callback

        btn = Button(
            size_hint=(None, None),
            size=(100, 100),
            background_normal=crop_tn_path,
            group='crops',
        )

        btn.bind(on_press=callback_factory(self, crop_path, yaw, lat, lon, orig_img))
        self.root.crops_gallery.stacked_layout.add_widget(btn)

    def QR_Decode(self):
        """First check if QR decode library is installed and get it's path"""
        if (self.config.get('CV', 'QR_lib_installed')) == "0":
            print "ERROR - zxing library not installed"
            self.root.crops_gallery.updateQRText("Cannot decode - please install decode library")
            return
        else:
            zxing_path = self.config.get('CV', 'QR_lib_path')
            if not os.path.exists(zxing_path):
                print "ERROR - zxing library path invalid"
                self.root.crops_gallery.updateQRText("Error")
                return

        import zxing

        """Try to decrypt a QRC target from the crops list"""
        barcode = None
        start_text = "Starting to Decode QR"
        print (start_text)
        self.root.crops_gallery.updateQRText(start_text)

        simg = self.root.crops_gallery.scatter_image
        if simg is None:
            return

        imgPath = simg.source
        if (imgPath == None):
            none_text = "QR error - image not found"
            print (none_text)
            self.root.crops_gallery.updateQRText(none_text)
            return

        # import and enhance image
        img = cv2.imread(imgPath, 0)
        enImg = cv2.add(img, -((np.max(img)) / 2))
        enImg = cv2.multiply(enImg, 1.4)
        memImg = enImg
        enImgPath = imgPath + r'_temp.jpg'
        cv2.imwrite(enImgPath, enImg)
        # initialize zXing library reader
        reader = zxing.BarCodeReader(zxing_path)
        for i in range(1, 90):
            # Try to decode the enhanced image
            barcode = reader.decode(enImgPath, try_harder=True)
            if barcode != None:
                break
            # rotation angle in degree
            enImg = ndimage.rotate(memImg, i)
            cv2.imwrite(enImgPath, enImg)
            rotation_txt = "Rotation by " + str(i) + " deg"
            print rotation_txt
            self.root.crops_gallery.updateQRText(rotation_txt)
        # Delete enhanced image in order for the GUI to reopen without crashing
        try:
            os.remove(enImgPath)
        except:
            pass
        # Print Code
        if barcode == None:
            print "No Code"
            self.root.crops_gallery.updateQRText("No Code")

        else:
            text = os.linesep.join([s for s in barcode.data.splitlines() if s])
            print barcode.data
            self.root.crops_gallery.updateQRText(text)

    def populateGalleryLists(self):
        """Populate the images list that were already downloaded."""

        #
        # Scan the images folder and load all images to the gallery
        #
        img_paths = sorted(glob.glob(os.path.join(gs.IMAGES_FOLDER, '*.jpg')))
        img_names = [os.path.splitext(os.path.split(path)[1])[0] for path in img_paths]
        data_paths = [os.path.join(gs.FLIGHTDATA_FOLDER, name+'.json') for name in img_names]
        img_tn_paths = [os.path.join(gs.THUMBNAILS_FOLDER, name+'_tn.jpg') for name in img_names]
        img_tn_pressed_paths = [os.path.join(gs.THUMBNAILS_FOLDER, name+'_pressed_tn.jpg') for name in img_names]

        client = server.getClient()

        for img_path, img_name, img_tn_path, img_tn_pressed_path, data_path in zip(img_paths, img_names, img_tn_paths, img_tn_pressed_paths, data_paths):
            self._populateImagesList(img_name + '.jpg', img_path, img_tn_path, img_tn_pressed_path, data_path)
            client.addExistingImg(img_name + '.jpg')

        #
        # Scan the crops folder and load all crops to the gallery
        #
        crop_paths = sorted(glob.glob(os.path.join(gs.CROPS_FOLDER, 'manual_*.jpg')))
        crop_names = [os.path.splitext(os.path.split(path)[1])[0] for path in crop_paths]
        data_paths = [os.path.join(gs.FLIGHTDATA_FOLDER, name+'.json') for name in crop_names]
        crop_tn_paths = [os.path.join(gs.THUMBNAILS_FOLDER, name+'_tn.jpg') for name in crop_names]

        for crop_path, crop_tn_path, data_path in zip(crop_paths, crop_tn_paths, data_paths):
            with open(data_path, 'rb') as f:
                crop_data = json.load(f)

            if not crop_data['auto']:
                self._populateCropsList(crop_path, crop_tn_path, crop_data['yaw'], crop_data['lat'], crop_data['lon'], crop_data['orig_img'])

    def updateTargetLocation(self, lat, lon):
        self.root.images_gallery.updateTargetLocation(lat, lon)

    def build_config(self, config):
        """Create the default config (used the first time the application is run)"""

        config.setdefaults(
            'Network', {'IP': '192.168.1.101', 'role': gs.PRIMARY, 'IP_CONTROLLER': '192.168.1.201'}
            )
        config.setdefaults(
            'Camera', {'ISO': 100, 'Shutter': 5000, 'Aperture': 4, 'Zoom': 45}
        )
        config.setdefaults(
            'Admin', {'Logging Path': gs.AUVSI_BASE_FOLDER}
        )
        config.setdefaults(
            'CV', {'image_rescaling': 0.25, 'QR_lib_installed': False, 'QR_lib_path': 'No_Path'}
        )
        config.setdefaults(
            'IMU', {'calib': False}
        )

        #
        # Disable multi touch emulation with the mouse.
        #
        from kivy.config import Config
        Config.set('input', 'mouse', 'mouse,disable_multitouch')

    def build_settings(self, settings):
        """Build the settings menu."""

        settings.add_json_panel("Network", self.config, data=network_json)
        settings.add_json_panel("Camera", self.config, data=camera_json)
        settings.add_json_panel("IMU", self.config, data=imu_json)
        settings.add_json_panel("CV", self.config, data=cv_json)
        settings.add_json_panel("Admin", self.config, data=admin_json)
        settings.add_json_panel("Version", self.config, data=version_json)

    def on_config_change(self, config, section, key, value):
        """Handle change in the settings."""

        if section == 'Network':
            self.connect_to_server()
        elif section == 'Camera':
            self._camera_send_settings()
        elif section == 'CV':
            args = {
                'image_rescaling': self.config.get('CV', 'image_rescaling'),
            }
            pass
        elif section == 'IMU':
            if self.config.get('IMU', 'calib'):
                self.calibrateIMU()
                self.config.set('IMU', 'calib', False)


        #
        # Re-request the keyboard as it is lost to the settings pannel.
        # NOTE:
        # This is a hack that I added, I am not sure it is the correct way to do.
        # Might help:
        # https://groups.google.com/forum/#!topic/kivy-users/eblh9FDBADs
        #
        self.root.images_gallery.scatter_image.setup_keyboard()

    def _camera_send_settings(self):
        args = {
            'ISO': self.config.get('Camera', 'iso'),
            'shutter': self.config.get('Camera', 'shutter'),
            'aperture': self.config.get('Camera', 'aperture'),
            'zoom': self.config.get('Camera', 'zoom'),
        }
        self.server.send_cmd('camera', 'set', **args)

    def connect_to_server(self):
        """Initiate connection to airborne server."""

        server.setserver(
            ip=self.config.get('Network', 'ip'),
            role=self.config.get('Network', 'role'),
            ip_controller=self.config.get('Network', 'ip_controller'),
        )
        self.server = server.connect(self, MyImagesClient)

    def on_connection(self):
        """Callback on successfull connection to the server."""

        self.root.connect_label.canvas.before.children[0].rgb = (0, 0, 1)
        self.root.connect_label.text = 'Connected'
        self.server.send_cmd('state')
        self._camera_send_settings()

    def on_disconnection(self):
        """Callback on disconnection from the server."""

        self.root.connect_label.canvas.before.children[0].rgb = (1, 0, 0)
        self.root.connect_label.text = 'Disconnected'

    def setDownloadState(self, downloading):
        self._updating_ui = True
        self.root.images_gallery.setDownloadState(downloading)
        self._updating_ui = False

    def setCameraState(self, shooting):
        self._updating_ui = True
        self.root.images_gallery.setCameraState(shooting)
        self._updating_ui = False

    def shoot(self, start_shooting):
        if not self._updating_ui:
            if start_shooting:
                self.server.send_cmd('camera', 'start')
            else:
                self.server.send_cmd('camera', 'off')

    def downloadImages(self, start_downloading):
        if not self._updating_ui:
            if start_downloading:
                self.server.send_cmd('download', 'start')
            else:
                self.server.send_cmd('download', 'off')

    def newMission(self):
        """Add a horizontal spacer to the images gallery to mark new mission"""

        self.root.images_gallery.stacked_layout.add_widget(MissionLabel(text='Mission #%d' % self.mission_cnt, font_size='20dp'))
        self.mission_cnt += 1

    def calibrateIMU(self):
        self.server.send_cmd('calibrate', 'imu')

    def setOriginalImage(self, img):
        self.original_img = img

    def showOriginalImage(self):
        if self.original_img is None or not self.original_img in self.img_buttons:
            return

        self.root.screen_manager.current = 'images'
        self.img_buttons[self.original_img].trigger_action(duration=0)

    # def getNextImage(self, image_name):
    #     if image_name not in self.img_buttons:
    #         return None
    #
    #     next = self.img_buttons._OrderedDict__map[image_name][1]
    #     if next is self.img_buttons._OrderedDict__root:
    #         return None
    #
    #     return next[2]
    #
    #
    # def getPrevImage(self, image_name):
    #     if image_name not in self.img_buttons:
    #         return None
    #
    #     prev = self.img_buttons._OrderedDict__map[image_name][0]
    #     if prev is self.img_buttons._OrderedDict__root:
    #         return None
    #
    #     return prev[2]

    def getNextImage(self, image_name):
        if image_name not in self.images:
            return None

        img = self.images[image_name]

        if img.queue_index < 0 or img.queue_index >= len(self.img_queue) - 1:
            return None

        return self.img_queue[img.queue_index + 1][0]


    def getPrevImage(self, image_name):
        if image_name not in self.images:
            return None

        img = self.images[image_name]

        if img.queue_index < 1 or img.queue_index >= len(self.img_queue):
            return None

        return self.img_queue[img.queue_index - 1][0]


    def setCurrentImg(self, keycode):

        if len(self.img_buttons) == 0:
            return

        if keycode == 'right':
            next_name = self.getNextImage(self.current_img_name)

            if next_name is None:
                return

            self.img_buttons[next_name].trigger_action(duration=0)
        if keycode == 'left':
            prev_name = self.getPrevImage(self.current_img_name)

            if prev_name is None:
                return

            self.img_buttons[prev_name].trigger_action(duration=0)

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
    GUIApp().run()
