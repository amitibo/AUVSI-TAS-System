#install_twisted_rector must be called before importing the reactor
from kivy.support import install_twisted_reactor
install_twisted_reactor()

from AUVSIground import server

from twisted.python import log
from twisted.internet.task import LoopingCall

from kivy.app import App
from kivy.uix.settings import SettingsWithTabbedPanel
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.uix.label import Label

from AUVSIground.widgets import *
from AUVSIground.utils import calculateOrientation

from AUVSIground.images_client import ImagesClient, AutoClient
import AUVSIground.global_settings as gs
import AUVSIcv

try:
    from shapely.geometry import Polygon
    from shapely.geometry import Point
    HAS_SHAPELY = True
except:
    HAS_SHAPELY = False

import pickle
import pkg_resources
import pandas as pd
from sklearn.cluster import DBSCAN
from random import random
from math import sqrt
from sys import stdout
import shutil
import glob
import json
import cv2
import os

from settingsjson import network_json, version_json

#
# TODO
# ----
# - Add button to compose the final targets with the manual targets.
# - Latitude and Longitude should be marked with minutes.seconds ...
#

class ADLCImagesClient(ImagesClient):
    """Handle the image/crops transfer from the airborne server."""

    def __init__(self, *params, **kwds):

        super(ADLCImagesClient, self). __init__(*params, **kwds)

    def handleNewADLCresults(self, analysis):

        file_path, results = pickle.loads(analysis[0])
        self.app.addADLCresults(file_path, results)

    def handleNewImg(self, new_img_message):
        """Handle the new image zmq message."""

        img_name, img_data, flight_data = new_img_message
        flight_data = json.loads(flight_data)

        #
        # Update the images database.
        #
        self.app.addImage(img_name, img_data, flight_data)

    def handleNewCrop(self, crop_type, new_crop_message):
        """Handle the new crop zmq message."""

        #
        # Manual crops are ignored.
        #
        if crop_type != gs.AUTO_CROP:
            return

        img_name = new_crop_message[0]
        coords = [c for c in new_crop_message[1:5]]
        yaw, lat, lon, crop_name, crop_data = new_crop_message[5:]

        #
        # Update the crops database.
        #
        self.app.addCrop(img_name, coords, crop_name, crop_data)


class ADLCGui(BoxLayout):
    connect_label = ObjectProperty()
    stacked_layout = ObjectProperty()
    adlc = ObjectProperty()


def coordsToInds(coords):
    """Convert between crop coords to index to crops table."""

    coords = [int(float(c)) for c in coords]

    return json.dumps(coords)


class AutoApp(App):
    """Main ADLC system application."""

    kv_directory = pkg_resources.resource_filename('AUVSIground', 'resources')
    connection = None
    title = 'AUTOMATIC DETECTION, LOCALIZATION, AND CLASSIFICATION'
    icon = pkg_resources.resource_filename('AUVSIground', 'resources/tyto_icon.png')

    def build(self):
        """Main build function of the Kivy application."""

        #
        # Setup logging.
        #
        if not os.path.exists(gs.AUVSI_AUTO_BASE_FOLDER):
            os.makedirs(gs.AUVSI_AUTO_BASE_FOLDER)
        if not os.path.exists(gs.CROPS_AUTO_FOLDER):
            os.makedirs(gs.CROPS_AUTO_FOLDER)
        if not os.path.exists(gs.AUTO_FOLDER):
            os.makedirs(gs.AUTO_FOLDER)

        log.startLogging(stdout)
        log.addObserver(
            log.FileLogObserver(
                file(os.path.join(gs.AUVSI_AUTO_BASE_FOLDER, 'server_auto.log'), 'a+')
                ).emit
        )

        self.settings_cls = SettingsWithTabbedPanel

        self._imgs_btns = {}
        
        self._loadSearchArea()
        
        #
        # Start up the local server.
        #
        self.connect_to_server()

        #
        # Load or create the analysis databases
        #
        if os.path.exists(gs.AUTO_IMAGE_DB_PATH):
            self.images_db = pd.read_csv(gs.AUTO_IMAGE_DB_PATH, index_col=0)
            self.crops_db = pd.read_csv(gs.AUTO_CROPS_DB_PATH, index_col=(0,1))

            #
            # Update the GUI.
            #
            for img_name in self.images_db.index:
                self.updateGUI(img_name)

            #
            # Choose the final targets.
            #
            self.updateFinalTargets()
        else:
            self.images_db = pd.DataFrame(columns=('img path', 'tn path', 'tn press path', 'data path', 'crops num'))
            crops_index = pd.MultiIndex(
                levels=[[],[]],
                labels=[[],[]],
                names=[u'img name', u'coords']
            )
            self.crops_db = pd.DataFrame(
                index = crops_index,
                columns=(
                    'latitude',
                    'longitude',
                    'shape',
                    'character',
                    'angle',
                    'crop path',
                    'shape color',
                    'character color',
                    'centroid latitude',
                    'centroid longitude',
                )
            )

        #
        # Start the loop for saving the pandas table
        #
        #
        # Start the task of sending images every 0.5 second.
        #
        self._update_tables = False        
        self._loop_task = LoopingCall(self._saveTables)
        self._loop_task.start(gs.AUTO_TABLES_SAVE_PERIOD)

    def build_config(self, config):
        """Create the default config (used the first time the application is run)"""

        config.setdefaults(
            'Network',
            {
                'IP': '192.168.1.100',
                'port': gs.CAMERA_CTL_PORT,
                'role': gs.SECONDARY,
                'IP_CONTROLLER': '192.168.1.101',
            }
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
            #port=self.config.getint('Network', 'port'),
            role=self.config.get('Network', 'role'),
            ip_controller=self.config.get('Network', 'ip_controller'),
        )
        self.server = server.connect(self, ADLCImagesClient)

    def on_connection(self):
        """Callback on successfull connection to the server."""

        self.root.connect_label.canvas.before.children[0].rgb = (0, 0, 1)
        self.root.connect_label.text = 'Connected'

    def on_disconnection(self):
        """Callback on disconnection from the server."""

        self.root.connect_label.canvas.before.children[0].rgb = (1, 0, 0)
        self.root.connect_label.text = 'Disconnected'

    def _loadSearchArea(self):
        """Load the search area."""
        
        self._search_area = None
        
        if not HAS_SHAPELY:
            return

        #
        # Load the search area.
        #
        try:
            data_path = pkg_resources.resource_filename('AUVSIground', 'resources/search_area.txt')

            coords = []
            with open(data_path, 'rb') as f:
                for line in f:
                    line = line.strip()
                    if line == '':
                        continue

                    coords.append(tuple(float(val) for val in line.split()))

            self._search_area = Polygon(coords)
        except Exception as e:
            log.err(e, 'Failed to load search area data')
            
    def _saveTables(self):
        """Save the images/crops tables."""
        
        #
        # Save the updated databases.
        #
        if not self._update_tables:
            return
        
        self._update_tables = False
        
        self.images_db.to_csv(gs.AUTO_IMAGE_DB_PATH)
        self.crops_db.to_csv(gs.AUTO_CROPS_DB_PATH)
    
    def updateADLCresultsDB(self, img_name, img_path, data_path, results):
        """Update the image database with a new analysis result"""

        #
        # First add the crops to the database (so that we can update the GUI)
        # NOTE:
        # This section assumes that the flight_data has arrived. Although
        # this is a reasonable assumtion, it can fail. For example, if the
        # user turns of the download of images. So in general this location
        # is prone for error.
        #
        # NOTE:
        # I am hard coding the height, so that there will be no need to 
        # load the image (time)
        #
        img_obj = AUVSIcv.Image(data_path=data_path, K=AUVSIcv.global_settings.resized_K)
        h = 1080

        requested_crops = []
        for result in results:
            #
            # Note:
            # coords2LatLon assumes the center of axes is at the bottom left of
            # the image. Therefore there is a need to flip the y coords.
            #
            coords = np.array(result['rect']).ravel()
            x, y = (coords[:2] + coords[2:])/2
            y = max(h-y-1, 0)
            lat, lon = img_obj.coords2LatLon(x, y)

            #
            # Check if the target is inside the search area.
            #
            if self._search_area is not None and not self._search_area.contains(Point(lat, lon)):
                #
                # Target is not inside search area, ignore it.
                # The motivation is to reduce false positive even in the danger of missing
                # a true target.
                #
                continue
            
            shape = AUVSIcv.global_settings.SHAPE_LABELS[
                np.argmax(result['shape'])
            ]
            if result['character'] is not None:
                if shape == "QRcode":
                    #
                    # In the case of QRcode, the character holds the message.
                    #
                    character = result['character']
                    yaw = None
                else:
                    #
                    # In the case of a geometric shape the characters holds
                    # the confidence scores.
                    #
                    character = AUVSIcv.global_settings.LETTER_LABELS[
                        np.argmax(result['character'])
                    ]
                    yaw = calculateOrientation(img_obj._yaw+result['angle'])
                requested_crops.append(coords)
            else:
                character = None
                yaw = None

            if result['color'] is None:
                shape_color = None
                char_color = None
            else:
                colors = result['color'][1:-1].split(',')
                char_color = colors[0].strip()
                shape_color = colors[1].strip()

            new_row = pd.Series(
                data=(lat, lon, shape, character, yaw, shape_color, char_color),
                index=('latitude', 'longitude', 'shape', 'character', 'angle', 'shape color', 'character color')
            )
            self.crops_db.loc[(img_name, coordsToInds(coords)),:] = new_row

        #
        # Sort the crops multiindex lexically to improve search performance.
        #
        self.crops_db = self.crops_db.sortlevel()
        
        #
        # Update the image db.
        #
        if img_name not in self.images_db.index:
            #
            # The image has yet to download (unlikely).
            #
            new_row = pd.Series(
                data=(len(results),),
                index=('crops num',)
            )
            new_row.name = img_name
            self.images_db = self.images_db.append(new_row)
        else:
            self.images_db['crops num'][img_name] = len(results)

        return requested_crops

    def downloadCrops(self, img_name, requested_crops):
        """Download a set of suspected target crops."""

        for coords in requested_crops:
            cmd = 'crop {img_name} {crop_type} {yaw} {lat} {lon} {coords}'.format(
                img_name=img_name,
                crop_type=gs.AUTO_CROP,
                yaw=0,
                lat=0,
                lon=0,
                coords=' '.join([str(c) for c in coords])
            )
            self.server.send_cmd(cmd)

    def addADLCresults(self, file_path, results):
        """Add new results from the ADLC to the database and GUI."""

        #
        # Some bookkeeping.
        #
        img_name = os.path.split(file_path)[1]
        if AUVSIcv.global_settings.ADLC_SEND_FULLSIZE:
            img_name = 'resized_'+img_name
        img_path = os.path.join(gs.AUTO_FOLDER, img_name)
        new_data = os.path.splitext(img_name)[0]+'.json'
        data_path = os.path.join(gs.AUTO_FOLDER, new_data)

        #
        # Add to results data base.
        #
        crops = self.updateADLCresultsDB(img_name, img_path, data_path, results)

        #
        # Save the updated databases.
        #
        self._update_tables = True

        #
        # Request for the full resolution crops
        #
        self.downloadCrops(img_name, crops)

        #
        # update gui
        #
        self.updateGUI(img_name)

    def updateGUI(self, img_name):
        """Add new image ADLC results to the GUI"""

        #
        # Check if all data relevant to the image
        # has arrived.
        #
        img_row = self.images_db.loc[(img_name,),:]
        if np.any(pd.isnull(img_row)):
            return

        #
        # Check if all requested crops were downloaded.
        #
        try:
            crops_df = self.crops_db.ix[(img_name,)]
            requested_inds = crops_df['character'].notnull()
            if np.any(pd.isnull(crops_df['crop path'][requested_inds])):
                return
        except:
            crops_df = None


        img_tn_path = img_row['tn path'][img_name]
        img_tn_pressed_path = img_row['tn press path'][img_name]

        def callback(instance):
            #
            # Update the title of the image.
            #
            self.root.adlc.image_name.text = os.path.splitext(img_name)[0]
            
            #
            # Show the image.
            #
            self.root.adlc.analysis_win.updateAnalysis(self.images_db['img path'][img_name], crops_df)
            self.root.adlc.sl_current_targets.clear_widgets()

            if crops_df is None:
                return

            #
            # Add the targets
            #
            requested_inds = crops_df['character'].notnull()
            for _, target_data in crops_df[requested_inds].iterrows():
                target = Target(
                    crop_path=target_data['crop path'],
                    target_shape=target_data['shape'],
                    bg_color=target_data['shape color'],
                    orient=target_data['angle'],
                    char=target_data['character'],
                    char_color=target_data['character color'],
                    latitude=target_data['latitude'],
                    longitude=target_data['longitude'],
                )
                self.root.adlc.sl_current_targets.add_widget(target)

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

        btn.bind(on_press=callback)
        self.root.adlc.sl_images.add_widget(btn)

        #
        # The button is stored for later reference.
        #
        self._imgs_btns[img_name] = btn
        
        #
        # If in liveupdate mode, trigger the button.
        #
        if self.root.adlc.live_btn.state == "down":
            btn.trigger_action()
            self.root.adlc.sv_images.scroll_to(btn)

    def addImage(self, img_name, img_data, flight_data):
        """Add a new image to the database and GUI"""

        #
        # Set paths
        #
        new_data = os.path.splitext(img_name)[0]+'.json'
        img_path = os.path.join(gs.AUTO_FOLDER, img_name)
        data_path = os.path.join(gs.AUTO_FOLDER, new_data)
        new_img_tn = '{}_tn{}'.format(*os.path.splitext(img_name))
        img_tn_path = os.path.join(gs.AUTO_FOLDER, new_img_tn)
        new_img_tn_pressed = '{}_pressed_tn{}'.format(*os.path.splitext(img_name))
        img_tn_pressed_path = os.path.join(gs.AUTO_FOLDER, new_img_tn_pressed)

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
        img_tn_pressed = img_tn.copy()[...,::-1]
        cv2.imwrite(img_tn_path, img_tn)
        cv2.imwrite(img_tn_pressed_path, img_tn_pressed)

        #
        # Update the image db.
        #
        new_row = pd.Series(
            data=(img_path, img_tn_path, img_tn_pressed_path, data_path),
            index=('img path', 'tn path', 'tn press path', 'data path')
        )
        new_row.name = img_name
        if img_name in self.images_db.index:
            #
            # The ADLC results already arrived (unlikely)
            #
            self.images_db.loc[(img_name,),:] = new_row

            #
            # Update the GUI
            #
            self.updateGUI(img_name)
        else:
            #
            # The ADLC results for this image is yet to arrive.
            #
            self.images_db = self.images_db.append(new_row)

        #
        # Save the updated databases.
        #
        self._update_tables = True

    def addCrop(self, img_name, coords, crop_name, crop_data):
        """Add a new crop to the database and GUI"""

        #
        # Calculate paths.
        #
        crop_path = os.path.join(gs.CROPS_AUTO_FOLDER, crop_name)

        #
        # Save crop
        #
        with open(crop_path, 'wb') as f:
            f.write(crop_data)

        log.msg('Finished Downloading crop {crop_path}'.format(crop_path=crop_path))

        #
        # Update the crop db.
        #
        self.crops_db.ix[(img_name, coordsToInds(coords)), 'crop path'] = crop_path

        #
        # Save the updated databases.
        #
        self._update_tables = True

        #
        # Self update the GUI.
        #
        self.updateGUI(img_name)

        #
        # Update the final targets.
        #
        self.updateFinalTargets()

    def translateShape(self, shape):
        d = {
            'circle' : ('STD', 'Circle'),
            'half circle': ('STD', 'Semicircle'),
            'quarter circle': ('STD', 'Quarter circle'),
            'rectangle' : ('STD', 'Rectangle'),
            'trapezoid': ('STD', 'Trapezoid'),
            'triangle': ('STD', 'Triangle'),
            'cross': ('STD', 'Cross'),
            'pentagon': ('STD', 'Pentagon'),
            'hexagon': ('STD', 'Hexagon'),
            'heptagon': ('STD', 'Heptagon'),
            'octagon': ('STD', 'Octagon'),
            'star': ('STD', 'Star'),
            'qrcode': ('QRC', '')
        }
        return d.get(shape.lower(), (None, None))

    def sendTarget(self, ind, crop):
        try:
            target_type, shape = self.translateShape(crop['shape'])
            shape_color = ''
            text = ''
            text_color = ''

            if target_type.lower() == 'std':
                shape_color = crop['shape color']
                text = crop['character']
                text_color = crop['character color']

            server.getClient().notifyTargetAuto(
                str(ind),
                crop['crop path'],
                0,
                crop['centroid latitude'],
                crop['centroid longitude'],
                target_type,
                shape,
                shape_color,
                text,
                text_color,
                crop['angle']
            )

        except Exception as e:
            log.err(e, 'Failed sending automatic target')

    def updateFinalTargets(self, maximal_distance=gs.SAME_TARGET_MAX_DISTANCE):
        #
        # Scan the crops data base for similar crops and form the final
        # targets.
        #
        downloaded_crops_inds = self.crops_db['crop path'].notnull()
        coordinates = self.crops_db[downloaded_crops_inds].as_matrix(columns=['latitude', 'longitude'])

        if coordinates.shape[0] == 0:
            return

        #
        # Calculate the clusters
        #
        db = DBSCAN(eps=maximal_distance, min_samples=1).fit(coordinates)
        labels = db.labels_
        num_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        clusters = pd.Series([coordinates[labels == i] for i in xrange(num_clusters)])

        #
        # Find the centers of the clustes.
        #
        for i, cluster in clusters.iteritems():
            centroid_lat, centroid_lon = getCentroid(cluster)
            centroid_inds = downloaded_crops_inds.copy()
            centroid_inds[downloaded_crops_inds] = labels == i
            self.crops_db.loc[centroid_inds, 'centroid latitude'] = centroid_lat
            self.crops_db.loc[centroid_inds, 'centroid longitude'] = centroid_lon

        def callbackGen(img_btn):
            def callback(instance):
                #
                # Set the image of the crop to the active (analyzed) one.
                #
                img_btn.trigger_action()
                self.root.adlc.sv_images.scroll_to(img_btn)
                
            return callback
        
        #
        # Add the buttons of the selected targets.
        # Use the image of the first target of the cluster.
        #
        self.root.adlc.sl_targets.clear_widgets()
        _, path_inds = np.unique(labels, return_index=True)
        for path_ind in path_inds:
            crop = self.crops_db[downloaded_crops_inds].ix[path_ind]
            try:
                self.sendTarget(path_ind, crop)
            except Exception as e:
                log.err(e, 'Failed sending auto target')

            #
            # Add target button
            #
            btn = Button(
                size_hint=(None, None),
                size=(40, 40),
                background_normal=crop['crop path'],
                border=(0, 0, 0, 0)
            )
            
            img_name = crop.name[0]            
            if img_name in self._imgs_btns.keys():
                btn.bind(on_release=callbackGen(self._imgs_btns[img_name]))
            else:
                log.msg('Failed to bind final target to image. Probably the image is yet to arrive.')
                
            self.root.adlc.sl_targets.add_widget(btn)

    def log_message(self, msg):
        """"""

        log.msg(msg)


def getCentroid(points):
    n = points.shape[0]
    sum_lat = np.sum(points[:, 0])
    sum_lon = np.sum(points[:, 1])
    return (sum_lat/n, sum_lon/n)


if __name__ == '__main__':
    AutoApp().run()
