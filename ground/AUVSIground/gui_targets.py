#install_twisted_rector must be called before importing the reactor
from kivy.support import install_twisted_reactor
install_twisted_reactor()

import server

from twisted.python import log

from kivy.app import App
from kivy.uix.settings import SettingsWithTabbedPanel
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.lang import Builder
from kivy.properties import StringProperty

from AUVSIground.widgets import *

from AUVSIground.images_client import ImagesClient
from AUVSIground.utils import decimal_to_minsec, calculateOrientation

import AUVSIcv
import pickle

import pkg_resources
import global_settings as gs
from random import random
from math import sqrt
from sys import stdout
import shutil
import glob
import json
import cv2
import os

from settingsjson import network_json, targets_json, version_json

Builder.load_string('''
<CommitPopup>:
    target_image: target_image
    cols:1
    BoxLayout:
        height: 100
        size_hint_y: None
        pos_hint: {"center_x": 0.5}

        RelativeLayout:
            id: target_rl

            ScatterStencil:
                id: target_scatter
                size_hint: None, None
                size: target_rl.size
                do_rotation: False
                auto_bring_to_front: False

                CropImage:
                    id: target_image
                    size: target_scatter.size

	Label:
		text: root.text
	GridLayout:
		cols: 2
		size_hint_y: None
		height: '44sp'
		Button:
			text: 'Yes'
			on_release: root.dispatch('on_answer', True)
		Button:
			text: 'No'
			on_release: root.dispatch('on_answer', False)
''')

class CommitPopup(GridLayout):
    text = StringProperty()
    target_image = ObjectProperty()

    def __init__(self, app=None, target=None, **kwargs):
        super(CommitPopup, self).__init__(**kwargs)
        self.register_event_type('on_answer')
        self._app = app
        self._target = target
        self._answered = False
        self.target_image.source = target.crop_path
        self.target_image.parent.rotation = 0 #-target.yaw
        self.text = 'Type: {target_type}\n'.format(target_type=target.type)
        self.text += 'Shape: {shape}\n'.format(shape=target.shape)
        self.text += 'Shape color: {shape_color}\n'.format(shape_color=target.shape_color)
        self.text += 'Text: {text}\n'.format(text=target.text)
        self.text += 'Text color: {text_color}\n'.format(text_color=target.text_color)
        self.text += 'Orientation: {orientation}\n'.format(orientation=target.orientation)
        self.text += 'Description: {desc}\n'.format(desc=target.desc)

        lat, lon = decimal_to_minsec(target.lat, target.lon)
        self.text += 'Latitude: {lat}\n'.format(lat=lat)
        self.text += 'Longitude: {lon}\n'.format(lon=lon)

    def open_popup(self, popup):
        self._popup = popup
        popup.open()

    def on_answer(self, *args):
        if self._answered:
            return

        self._answered = True

        if args[0] and self._app is not None and self._target is not None:
            self._app.commitTargetComplete(self._target)

        if self._popup is not None:
            self._popup.dismiss()


class Target:
    def __init__(self, crop_name, crop_path, crop_tn_path, yaw, lat, lon):
        self.crop_name = crop_name
        self.crop_path = crop_path
        self.crop_tn_path = crop_tn_path
        self.type = 'STD'
        self.yaw = yaw
        self.lat = lat
        self.lon = lon
        self.shape = ''
        self.shape_color = ''
        self.text = ''
        self.text_color = ''
        self.orientation = ''
        self.desc = ''
        self.btn = None
        self.committed = False
        self.committed_btn = None
        self.commit_index = 0
        self.adlc = False
        self.id = None

class Crop:
    def __init__(self, crop_name, crop_path, crop_tn_path, yaw, lat, lon, orig_img):
        self.name = crop_name
        self.path = crop_path
        self.tn_path = crop_tn_path
        self.yaw = yaw
        self.lat = lat
        self.lon = lon
        self.orig_img = orig_img

class TargetsImagesClient(ImagesClient):
    """Handle the image/crops transfer from the airborne server."""

    def __init__(self, *params, **kwds):
        super(TargetsImagesClient, self). __init__(*params, **kwds)

        self._crops = []
        self._pending_targets = {}
        self._auto_targets = []

    def handleNewCrop(self, crop_type, new_crop_message):
        """Handle the new crop zmq message."""

        #
        # Manual crops are ignored.
        #
        #if crop_type != gs.MANUAL_CROP:
        #    return
        is_auto = crop_type != gs.MANUAL_CROP

        #
        # coords are ignored in the case of manual crops.
        #
        orig_img = new_crop_message[0]
        yaw, lat, lon, crop_name, crop_data = new_crop_message[5:]

        #
        # Calculate paths.
        #
        crop_path = os.path.join(gs.TARGETS_FOLDER, crop_name)
        yaw = float(yaw)
        lat = float(lat)
        lon = float(lon)

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
        crop_tn_path = os.path.join(gs.THUMBNAILS_FOLDER, new_crop_tn)

        crop = cv2.imread(crop_path)
        crop_tn = cv2.resize(crop, (100, 100), interpolation=cv2.INTER_AREA)
        cv2.imwrite(crop_tn_path, crop_tn)

        data_name = os.path.splitext(crop_name)[0]+'.json'
        data_path = os.path.join(gs.FLIGHTDATA_FOLDER, data_name)
        crop_details = {'yaw':yaw, 'lat':lat, 'lon':lon, 'orig_img':orig_img, 'auto':is_auto}
        with open(data_path, 'wb') as f:
            json.dump(crop_details, f)

        self._crops.append(crop_name)

        #
        # Add the new crop to the GUI
        #
        if not is_auto:
            self.app._addCropToList(Crop(crop_name, crop_path, crop_tn_path, yaw, lat, lon, orig_img))

        if crop_name in self._pending_targets:
            messages = self._pending_targets[crop_name]

            for message in messages:
                self.handleNewTarget(message)

    def handleSyncCropResponse(self, message):
        log.msg('Got missing crop: {crop_name}'.format(crop_name=message[3]))
        self.handleNewCrop(gs.MANUAL_CROP, message)

    def handleSyncCropListResponse(self, message):
        log.msg('Got sync crop list response')
        sync_crops = message
        missing_crops = [crop for crop in sync_crops if crop not in self._crops]
        log.msg('Requesting {crop_count} missing crops'.format(crop_count=len(missing_crops)))
        for crop in missing_crops:
            log.msg('Requesting crop {crop_name}...'.format(crop_name=crop))
            self.requestSyncCrop(crop)

    def handleNewTarget(self, message):
        if message[0] != gs.TARGET_AUTO:
            return

        try:
            target_id, crop_path, crop_yaw, target_type, lat, lon, shape, shape_color, text, text_color, orientation_text = message[1:]
            crop_name = os.path.split(crop_path)[1]
            
            if target_id in self._auto_targets:
                return

            if crop_name not in self._crops:
                self._pending_targets.get(crop_name, []).append(message)
                return

            self._auto_targets.append(target_id)

            t = Target(crop_name, crop_path, None, float(crop_yaw), float(lat), float(lon))
            t.type = target_type
            t.shape = shape
            t.shape_color = shape_color
            t.text = text
            t.text_color = text_color
            t.orientation = orientation_text
            t.desc = 'Automatic detection'
            t.adlc = True
            t.id = target_id

            self.app.addAutoTarget(t)

        except Exception as e:
            log.err(e, 'Failed processing automatic target')

class TargetsGui(BoxLayout):
    connect_label = ObjectProperty()
    stacked_layout = ObjectProperty()
    layout = ObjectProperty()
    props = ObjectProperty()


#class Target(BoxLayout):
#    target_image = ObjectProperty()


class TargetsApp(App):
    kv_directory = pkg_resources.resource_filename('AUVSIground', 'resources')
    connection = None
    title = 'Target selection'
    icon = pkg_resources.resource_filename('AUVSIground', 'resources/tyto_icon.png')
    selected_crop = None
    selected_target = None
    targets = []
    committed_targets = []
    auto_targets = {}
    final_targets = []

    def build(self):
        """Main build function of the Kivy application."""

        #
        # Setup logging.
        #
        if not os.path.exists(gs.AUVSI_BASE_FOLDER):
            os.makedirs(gs.AUVSI_BASE_FOLDER)
        if not os.path.exists(gs.TARGETS_FOLDER):
            os.makedirs(gs.TARGETS_FOLDER)

        log.startLogging(stdout)
        log.addObserver(
            log.FileLogObserver(
                file(os.path.join(gs.AUVSI_BASE_FOLDER, 'server_targets.log'), 'a+')
                ).emit
        )

        self.settings_cls = SettingsWithTabbedPanel

        #
        # Start up the local server.
        #
        self.connect_to_server()

    def build_config(self, config):
        """Create the default config (used the first time the application is run)"""

        config.setdefaults(
            'Network', {'IP': '192.168.1.100', 'port': gs.CAMERA_CTL_PORT, 'role': gs.SECONDARY, 'IP_CONTROLLER': '192.168.1.101'},
            )
        config.setdefaults(
            'Targets', {'export_path': 'C:\\TAS.txt', 'export_path_backup': 'C:\\TAS.txt', 'interop_path': 'C:\\Auto_Targets.txt'}
            )

        #
        # Disable multi touch emulation with the mouse.
        #
        from kivy.config import Config
        Config.set('input', 'mouse', 'mouse,disable_multitouch')

    def build_settings(self, settings):
        """Build the settings menu."""

        settings.add_json_panel("Network", self.config, data=network_json)
        settings.add_json_panel("Targets", self.config, data=targets_json)
        settings.add_json_panel("Version", self.config, data=version_json)

    def on_config_change(self, config, section, key, value):
        """Handle change in the settings."""

        if section == 'Network':
            self.connect_to_server()

    def connect_to_server(self):
        """Initiate connection to airborne server."""

        server.setserver(
            ip=self.config.get('Network', 'ip'),
            #port=self.config.getint('Network', 'port'),
            role=self.config.get('Network', 'role'),
            ip_controller=self.config.get('Network', 'ip_controller'),
        )
        self.server = server.connect(self, TargetsImagesClient)

    def on_connection(self):
        """Callback on successfull connection to the server."""

        self.root.connect_label.canvas.before.children[0].rgb = (0, 0, 1)
        self.root.connect_label.text = 'Connected'

    def on_disconnection(self):
        """Callback on disconnection from the server."""

        self.root.connect_label.canvas.before.children[0].rgb = (1, 0, 0)
        self.root.connect_label.text = 'Disconnected'

    def _addCropToList(self, crop):
        """Store new crop paths in crops list."""

        def callback_factory(crop):

            def callback(instance):
                self.selected_crop = crop
                self.root.layout.updateCrop(crop)
                #self.root.crops_gallery.updateTargetLocation(crop_lat, crop_lon)

            return callback

        btn = Button(
            size_hint=(None, None),
            size=(100, 100),
            background_normal=crop.tn_path,
            group='crops',
        )

        btn.bind(on_press=callback_factory(crop))
        self.root.layout.crops.add_widget(btn)

    def _addTargetToList(self, target):
        def callback_factory(target):

            def callback(instance):
                self.selected_target = None
                self.root.layout.updateTarget(target)
                self.root.props.updateTarget(target)
                self.selected_target = target
                #self.root.crops_gallery.updateTargetLocation(crop_lat, crop_lon)

            return callback

        btn = Button(
            size_hint=(None, None),
            size=(100, 100),
            background_normal=target.crop_tn_path,
            group='targets',
        )

        target.btn = btn
        self.targets.append(target)

        btn.bind(on_press=callback_factory(target))
        self.root.layout.targets.add_widget(btn)
        self.saveTargets()

    def _addCommittedTargetToList(self, target):
        def callback_factory(target):

            def callback(instance):
                self.selected_target = None
                self.root.layout.updateTarget(target)
                self.root.props.updateTarget(target)
                self.selected_target = target
                #self.root.crops_gallery.updateTargetLocation(crop_lat, crop_lon)

            return callback

        btn = Button(
            size_hint=(None, None),
            size=(100, 100),
            text_size = (100, 100),
            background_normal=target.crop_tn_path,
            group='targets',
            halign='left',
            valign='top',
            text='[b][color=ff0000]{index}[/color][/b]'.format(index=target.commit_index),
            markup=True
        )

        target.committed_btn = btn

        btn.bind(on_press=callback_factory(target))
        self.root.layout.committed_targets.add_widget(btn)
        self.saveTargets()

    def newTarget(self):
        if self.selected_crop is None:
            return

        crop = self.selected_crop
        target = Target(crop.name, crop.path, crop.tn_path, crop.yaw, crop.lat, crop.lon)
        #target.target_image.source = crop.path
        #self.root.stacked_layout.add_widget(target)
        self._addTargetToList(target)

        target.btn.trigger_action(duration=0)

    def commitTarget(self):
        if self.selected_target is None:
            return

        target = self.selected_target

        if target.committed:
            log.msg('Target already committed')
            return

        content = CommitPopup(text='Target details', app=self, target=target)
        #content.bind(on_answer=self._on_answer)
        popup = Popup(title='Are you sure you want to commit this target?',
                            content=content,
                            size_hint=(None, None),
                            size=(480,400),
                            auto_dismiss= False)
        content.open_popup(popup)

    def commitTargetComplete(self, target):
        target.committed = True
        target.commit_index = len(self.final_targets) + 1
        target.btn.background_color = [0.5, 0.5, 0.5, 1]
        target.btn.text_size = target.btn.size
        target.btn.halign = 'right'
        target.btn.valign = 'bottom'
        target.btn.text = '[b][color=ff0000]{index}[/color][/b] '.format(index=target.commit_index)
        target.btn.markup = True

        self.committed_targets.append(target)
        self.final_targets.append(target)
        self._addCommittedTargetToList(target)

        try:
            server.getClient().notifyTargetManual(
                target.crop_name,
                target.yaw,
                target.lat,
                target.lon,
                target.type,
                target.shape,
                target.shape_color,
                target.text,
                target.text_color,
                target.orientation,
                target.desc
            )
        except Exception as e:
            log.err(e, 'Failed sending notification for committed target')

    def addAutoTarget(self, target):
        if not target.id in self.auto_targets:
            target.committed = True
            target.commit_index = len(self.final_targets) + 1

            if target.id is not None:
                self.auto_targets[target.id] = target

            self.final_targets.append(target)
            self.saveTargets()


    def updateTargetCrop(self):
        if self.selected_crop is None or self.selected_target is None:
            return

        if self.selected_target.committed:
            log.msg('Cannot update committed target')
            return

        self.selected_target.lat = self.selected_crop.lat
        self.selected_target.lon = self.selected_crop.lon
        self.selected_target.crop_name = self.selected_crop.name
        self.selected_target.crop_path = self.selected_crop.path
        self.selected_target.crop_tn_path = self.selected_crop.path

        if self.selected_target.btn is not None:
            self.selected_target.btn.background_normal = self.selected_target.crop_tn_path

        self.root.layout.updateTarget(self.selected_target)
        self.root.props.updateTarget(self.selected_target)
        self.saveTargets()

    def updateTargetProps(self):
        if self.selected_target is None:
            return

        if self.selected_target.committed:
            log.msg('Cannot update committed target')
            return

        self.root.props.saveToTarget(self.selected_target)
        self.saveTargets()

    def log_message(self, msg):
        """"""

        log.msg(msg)

    def translateTargetType(self, type):
        d = { 'std': 'standard', 'qrc': 'qrc', 'oax': 'off_axis', 'emg': 'emergent' }
        return d.get(type.lower(), 'standard')

    def translateShape(self, shape):
        d = {
            'circle': 'circle', 'semicircle': 'semicircle', 'quarter circle': 'quarter_circle', 'triangle': 'triangle',
            'square': 'square', 'rectangle': 'rectangle', 'trapezoid': 'trapezoid', 'pentagon': 'pentagon',
            'hexagon': 'hexagon', 'heptagon': 'heptagon', 'octagon': 'octagon', 'star': 'star', 'cross': 'cross'
        }
        return d.get(shape.lower(), 'circle')

    def translateColor(self, shape):
        d = {
            'white': 'white', 'black': 'black', 'gray': 'gray', 'red': 'red',
            'blue': 'blue', 'green': 'green', 'yellow': 'yellow', 'purple': 'purple',
            'brown': 'brown', 'orange': 'orange'
        }
        return d.get(shape.lower(), 'black')

    def saveTargetsFile(self, path, format):
        log.msg('Writing targets to {path}'.format(path=path))

        dir_path, name = os.path.split(path)

        try:
            with open(path, 'w') as f:
                index = 1

                for target in self.final_targets:
                    try:
                        target_index = target.commit_index if format == 'interop' else index
                        new_crop_name = 'T{index}.jpg'.format(index=target_index)
                        new_crop_path = os.path.join(dir_path, new_crop_name)
                        shutil.copyfile(target.crop_path, new_crop_path)

                        if format == 'interop':
                            lat, lon = str(target.lat), str(target.lon)
                            target_type = self.translateTargetType(target.type)
                            shape = self.translateShape(target.shape)
                            shape_color = self.translateColor(target.shape_color)
                            text_color = self.translateColor(target.text_color)
                        else:
                            lat, lon = decimal_to_minsec(target.lat, target.lon)
                            target_type = target.type
                            shape = target.shape
                            shape_color = target.shape_color
                            text_color = target.text_color

                        if target.adlc:
                            desc = 'Automatic detection'
                        else:
                            desc = target.desc

                        line = '%02d\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' % (
                            target_index,
                            target_type,
                            lat,
                            lon,
                            target.orientation,
                            shape,
                            shape_color,
                            target.text,
                            text_color,
                            new_crop_name,
                            desc
                        )
                        f.write(line)

                        index += 1

                    except Exception as e:
                        log.err(e, 'Cannot write target information')

        except Exception as e:
            log.err(e, 'Cannot export target file')

    def saveTargets(self):
        self.saveTargetsFile(self.config.get('Targets', 'export_path'), 'default')
        self.saveTargetsFile(self.config.get('Targets', 'interop_path'), 'interop')

        backup_path = self.config.get('Targets', 'export_path_backup')

        if backup_path:
            self.saveTargetsFile(backup_path, 'default')

if __name__ == '__main__':
    TargetsApp().run()
