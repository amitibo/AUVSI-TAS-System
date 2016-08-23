'''
start_map
=========

Stitch the images based on their flight data.
'''

from __future__ import division
#install_twisted_rector must be called before importing the reactor
from kivy.support import install_twisted_reactor
install_twisted_reactor()

from AUVSIground.widgets import *

import numpy as np
from kivy.uix.settings import SettingsWithTabbedPanel
from kivy.app import App
import global_settings as gs
from images_client import ImagesClient
import StringIO
from PIL import Image
import pkg_resources
import tempfile
import AUVSIcv
import shutil
import glob
import json
import os
from math import pi


from settingsjson import network_json, version_json
from settingsjson import network_json, mp_json


class MyImagesClient(ImagesClient):
    """Handle the image/crops transfer from the airborne server."""

    def __init__(self, *params, **kwds):

        super(MyImagesClient, self). __init__(*params, **kwds)

        self._temp_folder = tempfile.mkdtemp()
        self._images = []

    def __del__(self, *params, **kwds):

        super(MyImagesClient, self). __del__(*params, **kwds)

        shutil.rmtree(self._temp_folder)

    def handleNewImg(self, new_img_message):
        """Handle the new image zmq message."""

        img_name, img_data, flight_data = new_img_message
        flight_data = json.loads(flight_data)

        img_path = os.path.join(self._temp_folder, img_name)
        data_path =  os.path.splitext(img_path)[0]+'.json'

        #
        # Load the image directly into a buffer
        # and resize it.
        #
        buff = StringIO.StringIO(buf=img_data)
        img = Image.open(buff)
        img.thumbnail(
            (AUVSIcv.global_settings.MAP_SIZE, AUVSIcv.global_settings.MAP_SIZE),
            Image.ANTIALIAS
        )
        img.save(img_path, "JPEG")

        #
        # Save flight data
        #
        with open(data_path, 'wb') as f:
            json.dump(flight_data, f)

        self._images.append(img_name)

        #
        # Update the map
        #
        self.app.addImage(img_path, data_path)

    def handleSyncImageResponse(self, message):
        log.msg('Got missing image: {img_name}'.format(img_name=message[0]))
        self.handleNewImg(message)

    def handleSyncImageListResponse(self, message):
        log.msg('Got sync image list response')
        sync_images = message
        missing_images = [img for img in sync_images if img not in self._images]
        log.msg('Requesting {img_count} missing images'.format(img_count=len(missing_images)))
        for img in missing_images:
            log.msg('Requesting image {img_name}...'.format(img_name=img))
            self.requestSyncImage(img)


class MapApp(App):
    """Map application"""

    quad_index = 0
    images_client = None
    kv_directory = pkg_resources.resource_filename('AUVSIground', 'resources')

    def build(self):

        self.settings_cls = SettingsWithTabbedPanel

        self.readPropertiesFromFiles()
        #
        # Populate the map with images already downloaded (if available).
        #
        if os.path.exists(gs.IMAGES_FOLDER):
            img_paths = sorted(glob.glob(os.path.join(gs.IMAGES_FOLDER, '*.jpg')))
            img_names = [os.path.splitext(os.path.split(path)[1])[0] for path in img_paths]
            img_tn_paths = [os.path.join(gs.THUMBNAILS_FOLDER, name+'_tn.jpg') for name in img_names]
            data_paths = [os.path.join(gs.FLIGHTDATA_FOLDER, name+'.json') for name in img_names]

            for img_path_tn, data_path,img_path  in zip(img_tn_paths, data_paths,img_paths):
                self.addImage(img_path_tn, data_path, img_path, toRedraw=False)
            self.root.map_widget.redrawLinesOfButtons()

        self.connect_to_server()

        #
        # Disable multi touch emulation with the mouse.
        #
        from kivy.config import Config
        Config.set('input', 'mouse', 'mouse,disable_multitouch')

    def readPropertiesFromFiles(self):
        files = []
        files.append('resources/search_area.txt')
        files.append('resources/flight_boundary.txt')
        files.append('resources/search_path.txt')
        files.append('resources/obstacles.txt')
        for curr_file in files:

            if curr_file == 'resources/obstacles.txt':
                with_radius = True
            else:
                with_radius = False

            properties = self.root.map_widget.getCoordsFromFile(curr_file, with_radius)

            #
            # Load the file
            #
            try:
                if curr_file == 'resources/search_area.txt':
                    self.root.map_widget.setSearchArea(properties)
                elif curr_file == 'resources/flight_boundary.txt':
                    self.root.map_widget.setFlightBoundary(properties)
                elif curr_file == 'resources/search_path.txt':
                    self.root.map_widget.setSearchPath(properties)
                elif curr_file == 'resources/obstacles.txt':
                    self.root.map_widget.setObstacles(properties)
            except:
                log.msg('Failed to load file :' + str(curr_file))
        self.root.map_widget.set_grid()
    def build_settings(self, settings):
        """Build the settings menu."""

        settings.add_json_panel("Network", self.config, data=network_json)
        settings.add_json_panel("Version", self.config, data=version_json)
        settings.add_json_panel("MP", self.config, data=mp_json)

    def build_config(self, config):
        """Create the default config (used the first time the application is run)"""

        config.setdefaults(
            'Network',
            {
                'IP': '192.168.1.101',
                'role': gs.SECONDARY,
                'IP_CONTROLLER': '192.168.1.201'
            }
        )

        config.setdefaults(
            'MP',
            {
                'mp_ip': '192.168.1.101',
                'mp_folder': 'Default',
                'mp_gps': '10',
                'mp_grid_cell_height': '60',
                'mp_grid_cell_width': '60'
            }
        )

    def on_config_change(self, config, section, key, value):
        """Handle change in the settings."""

        if section == 'Network':
            self.connect_to_server()

    def addImage(self, img_path, data_path, img_path_full_size=None, toRedraw=True):
        """Add an image to the map"""

        img = AUVSIcv.Image(
            img_path,
            data_path,
            img_path_full_size=img_path_full_size,
            K=AUVSIcv.global_settings.map_K
        )

        #
        # Filter image based on roll of plane
        # TODO:
        # See if this is still necessary with the new Gimbal.
        #
        if abs(img.plane['roll']) < 15./180*pi and abs(img.plane['roll']) < 15./180*pi and (img.stitching_pic_OK == 1):
            log.msg("Adding image, roll: {}".format(img._roll))
            self.root.map_widget.addImage(img, toRedraw)
        else:
            log.msg("Discarding image, roll: {}".format(img._roll))

    def connect_to_server(self):
        """Connect to the primary image server"""

        if self.images_client is not None:
            self.images_client.shutdown()

        #
        # Setup the Images client.
        #
        self.images_client = MyImagesClient(
            app=self,
            ip_camera=self.config.get('Network', 'ip'),
            role=gs.SECONDARY,
            ip_controller=self.config.get('Network', 'ip_controller'),
        )

    def updateLocationOnMap(self, lat, lon):
        """Update the controls showing pressed location."""

        self.root.updateLocationOnMap(lat, lon)

    #
    # Functions for Buttons
    #
    def get_button_state(self, button):
        if button == 'flight_boundary':
            return self.root.flight_boundary.state == 'down'
        elif button == 'search_area':
            return self.root.search_area.state == 'down'
        elif button == 'search_path':
            return self.root.search_path.state == 'down'
        elif button == 'Targets':
            return self.root.Targets.state == 'down'
        elif button == 'grid':
            return self.root.grid.state == 'down'
        elif button == 'points_gps':
            return self.root.points_gps.state == 'down'
        elif button == 'obstacles':
            return self.root.obstacles.state == 'down'
        else:
            print "get_button_state : no such button"
            return None

    def press_button(self, button, show):
        if button == 'flight_boundary':
            self.root.map_widget.draw_flight_boundary(show)
        elif button == 'search_area':
            self.root.map_widget.draw_search_area(show)
        elif button == 'search_path':
            self.root.map_widget.draw_search_path(show)
        elif button == 'Targets':
            print "press_button : Targets : function does not exist yet"
        elif button == 'grid':
            self.root.map_widget.draw_grid(show)
        elif button == 'points_gps':
            self.root.map_widget.draw_GPS_points(show)
        elif button == 'obstacles':
            self.root.map_widget.draw_obstacles(show)
        else:
            print "press_button : no such button"


    def update(self):
        IP = self.config.get('MP', 'mp_ip')
        print IP
        FOLDER = self.config.get('MP', 'mp_folder')
        print FOLDER
        PATH = r'\\'+IP+r'\\'+FOLDER
        #print os.path.isdir(PATH)

        # search area
        if App.get_running_app().get_button_state('search_area'):
            self.root.map_widget.draw_search_area(False)
        # flight boundary
        if App.get_running_app().get_button_state('flight_boundary'):
            self.root.map_widget.draw_flight_boundary(False)
        # search path
        if App.get_running_app().get_button_state('search_path'):
            self.root.map_widget.draw_search_path(False)
        # Obstacles
        if App.get_running_app().get_button_state('obstacles'):
            self.root.map_widget.draw_obstacles(False)
        if App.get_running_app().get_button_state('grid'):
            self.root.map_widget.draw_grid(False)

        #set data from file s
        self.readPropertiesFromFiles()

        # search area
        if not App.get_running_app().get_button_state('search_area'):
            self.root.map_widget.draw_search_area(False)
        # flight boundary
        if not App.get_running_app().get_button_state('flight_boundary'):
            self.root.map_widget.draw_flight_boundary(False)
        # search path
        if not App.get_running_app().get_button_state('search_path'):
            self.root.map_widget.draw_search_path(False)
        # Obstacles
        if not App.get_running_app().get_button_state('obstacles'):
            self.root.map_widget.draw_obstacles(False)
        if not App.get_running_app().get_button_state('grid'):
            self.root.map_widget.draw_grid(False)



