from __future__ import division
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.properties import ObjectProperty
from kivy.uix.stencilview import StencilView
from kivy.graphics import Color, Rectangle, Quad, Line
from kivy.uix.image import Image, AsyncImage
from kivy.uix.scatter import Scatter
from kivy.core.window import Window
from kivy.uix.dropdown import DropDown
from kivy.uix.textinput import TextInput
from kivy.properties import ListProperty
from kivy.app import App
from stitching.PicturesData import PicturesData
from stitching.Area import Area
import pkg_resources
from twisted.python import log
import json

from AUVSIground.utils import decimal_to_minsec
import global_settings as gs
import numpy as np
import datetime
import AUVSIcv

RESIZED_SCALE = 1080 / 4000


######################################################################
# Widgets for the Main gui.
######################################################################
class MissionLabel(Label):
    def __init__(self, **kwargs):
        super(MissionLabel, self).__init__(**kwargs)
        self.size_hint_y = None
        self.height = 30


class BGLabel(Label):
    pass


class BoxStencil(BoxLayout, StencilView):
    pass


class ScatterStencil(Scatter):
    """A scatter object that is collide aware to its parent stencil."""

    def on_touch_down(self, touch):
        stencil = self.parent.parent

        #
        # Check if inside the encapsulating stencil.
        #
        if not stencil.collide_point(*self.to_window(*touch.pos)):
            return False

        return super(ScatterStencil, self).on_touch_down(touch)


class ImageAction(object):
    def __init__(self, widget, touch, img_obj):
        self._widget = widget
        self._group = str(touch.uid)
        self.img_obj = img_obj

    def pos_to_texture(self, pos, flip_y=False):
        offset_x = self._widget.center[0] - self._widget.norm_image_size[0] / 2
        offset_y = self._widget.center[1] - self._widget.norm_image_size[1] / 2

        scale_ratio = self._widget.texture_size[0] / self._widget.norm_image_size[0]

        texture_x = (pos[0] - offset_x) * scale_ratio
        texture_y = (pos[1] - offset_y) * scale_ratio

        #
        # Flip the y coord (the kivy pos coords start at bottom while the image's coords start at top).
        #
        if flip_y:
            texture_y = max(self._widget.texture_size[1] - texture_y - 1, 0)

        return texture_x, texture_y


class CoordsAction(ImageAction):
    def __init__(self, widget, touch, img_obj):
        super(CoordsAction, self).__init__(widget, touch, img_obj)

        win = widget.get_parent_window()

        with self._widget.canvas:
            Color(1, 1, 1, mode='hsv', group=self._group)
            self._lines = [
                Rectangle(pos=(touch.x, 0), size=(1, win.height), group=self._group),
                Rectangle(pos=(0, touch.y), size=(win.width, 1), group=self._group),
            ]

        self.update_target(touch)

    #
    # Nitzan: The section below was commented out because it caused a bug where coords moved with mouse cursor.
    # Also commented out the call to this function in TouchAsyncImage - on_touch_move
    #
    def on_touch_move(self, touch):
        if touch.button == 'left':
            self._lines[0].pos = touch.x, 0
            self._lines[1].pos = 0, touch.y
            self.update_target(touch)

    def on_touch_up(self, touch):
        self._widget.canvas.remove_group(self._group)

    def update_target(self, touch):
        if self.img_obj is None:
            return

        #
        # Note:
        # Here we are interested in the texture (kivy) coords. So we don't need to
        # flip the y.
        #
        lat, lon = self.img_obj.coords2LatLon(*self.pos_to_texture(touch.pos, flip_y=False))

        App.get_running_app().updateTargetLocation(lat, lon)


class MapCoordsAction(object):
    """Handle the action of map coordinates update."""

    def __init__(self, widget, touch):
        self._widget = widget
        self._group = str(touch.uid)

        # win = widget.get_parent_window()
        h = (widget.top - widget.y) / widget.scale
        w = (widget.right - widget.x) / widget.scale

        with self._widget.parent.canvas:
            Color(1, 1, 1, mode='hsv', group=self._group)
            self._widget._lines = [
                Rectangle(pos=(touch.x, 0), size=(1, h), group=self._group),
                Rectangle(pos=(0, touch.y), size=(w, 1), group=self._group),
            ]

        self.updateMap(touch)

    def on_touch_move(self, touch):
        self._lines[0].pos = touch.x, 0
        self._lines[1].pos = 0, touch.y

        self.updateMap(touch)

    def on_touch_up(self, touch):
        self._widget.parent.canvas.remove_group(self._group)

    def updateMap(self, touch):
        absolute_pos = np.subtract(touch.pos, self._widget.pos) / self._widget.scale
        print absolute_pos
        pos = tuple(self._widget.ned.ned2geodetic([absolute_pos[1], absolute_pos[0], 0]))
        App.get_running_app().updateLocationOnMap(pos[0], pos[1])


class CropAction(ImageAction):
    def __init__(self, widget, touch, img_obj):

        super(CropAction, self).__init__(widget, touch, img_obj)

        self._start_pos = touch.pos
        with self._widget.canvas:
            Color(0, 0, 1, .5, mode='rgba', group=self._group)
            self._rect = \
                Rectangle(pos=self._start_pos, size=(1, 1), group=self._group)

    def on_touch_move(self, touch):

        self._rect.size = [c - s for c, s in zip(touch.pos, self._start_pos)]

    def on_touch_up(self, touch):

        self._widget.canvas.remove_group(self._group)

        if self.img_obj is None:
            return

        #
        # Note:
        # Here we are interested in the image coords. So we need to
        # flip the y.
        #
        start_XY = self.pos_to_texture(self._start_pos, flip_y=True)
        end_XY = self.pos_to_texture(touch.pos, flip_y=True)

        coords = (
            min(start_XY[0], end_XY[0]),
            min(start_XY[1], end_XY[1]),
            max(start_XY[0], end_XY[0]),
            max(start_XY[1], end_XY[1]),
        )

        #
        # Check validity of the crops
        #
        if (coords[2] - coords[0]) < gs.MINIMAL_CROP_SIZE or (coords[3] - coords[1]) < gs.MINIMAL_CROP_SIZE:
            log.msg('Crop coords too small {}, not sending command.'.format(coords))
            return

        #
        # Calculate the latitude and longitude of the crops center.
        # Here we are interested in the texture coords so we repeat the 
        # conversion this time we don't flip the y.
        #
        x0, y0 = self.pos_to_texture(self._start_pos, flip_y=False)
        x1, y1 = self.pos_to_texture(touch.pos, flip_y=False)
        
        lat, lon = self.img_obj.coords2LatLon((x0+x1)/2, (y0+y1)/2)

        cmd = 'crop {img_name} {crop_type} {yaw} {lat} {lon} {coords}'.format(
            img_name=self.img_obj.name,
            crop_type=gs.MANUAL_CROP,
            yaw=self.img_obj._yaw,
            lat=lat,
            lon=lon,
            coords=' '.join([str(c) for c in coords])
        )
        App.get_running_app().server.send_cmd(cmd)


class TouchAsyncImage(AsyncImage):
    def __init__(self, *args, **kwargs):
        super(TouchAsyncImage, self).__init__(*args, **kwargs)
        self.img_obj = None
        self._keyboard = None

        self.setup_keyboard()

    def setup_keyboard(self):
        if self._keyboard is not None:
            return

        self._keyboard = Window.request_keyboard(self._keyboard_closed, self)
        self._keyboard.bind(on_key_down=self._on_keyboard_down)
        self._keyboard.bind(on_key_up=self._on_keyboard_up)
        self._ctrl_held = False

    def _keyboard_closed(self):
        self._keyboard.unbind(on_key_down=self._on_keyboard_down)
        self._keyboard = None

    def _on_keyboard_down(self, keyboard, keycode, text, modifiers):
        if keycode[1] in ("ctrl", "rctrl", "lctrl"):
            #
            # Activate the crop mode
            #
            self._ctrl_held = True
        elif keycode[1] in ('left', 'right'):
            #
            # Browse the images using the keyboard arrows
            #
            App.get_running_app().setCurrentImg(keycode[1])
            #
            # Reset the scatter size and position, when image change
            #
            self.parent.scale = 1.0
            self.parent.pos = (0, 0)

        elif keycode[1] in ('r', 'R'):
            #
            # Reset the scatter size and position
            #
            self.parent.scale = 1.0
            self.parent.pos = (0, 0)

        return True

    def _on_keyboard_up(self, *args, **kwargs):
        self._ctrl_held = False

        return True


    def on_touch_down(self, touch):

        #
        # Check if mouse event
        #
        if touch.device == 'mouse':

            if touch.button in ('scrolldown', 'scrollup'):
                #
                # Check if the scroll wheel is used
                #
                if touch.button == 'scrolldown' and self.parent.scale > 0.6:
                    self.parent.scale -= 0.1
                elif touch.button == 'scrollup':
                    self.parent.scale += 0.1

            elif touch.button == 'right':
                touch.grab(self)
                touch.ud['action'] = CoordsAction(self, touch, self.img_obj)

            elif touch.button == 'left' and self._ctrl_held:
                touch.grab(self)
                touch.ud['action'] = CropAction(self, touch, self.img_obj)
                return True

            return super(TouchAsyncImage, self).on_touch_down(touch)

        return super(TouchAsyncImage, self).on_touch_down(touch)

    def on_touch_move(self, touch):

        if touch.grab_current is not self:
            return super(TouchAsyncImage, self).on_touch_move(touch)

        #
        # Nitzan: The line below was commented out because it caused a bug where coords moved with mouse cursor.
        # Also commented out the call to on_touch_move in CoordsAction class
        #
        touch.ud['action'].on_touch_move(touch)

        return super(TouchAsyncImage, self).on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is not self:
            return super(TouchAsyncImage, self).on_touch_up(touch)

        touch.ud['action'].on_touch_up(touch)
        touch.ud['action'] = None

        touch.ungrab(self)

        return super(TouchAsyncImage, self).on_touch_up(touch)


class CropImage(AsyncImage):
    def on_touch_down(self, touch):

        #
        # Check if mouse event
        #
        if touch.device == 'mouse' and touch.button in ('scrolldown', 'scrollup'):

            #
            # Check if the scroll wheel is used
            #
            if touch.button == 'scrolldown' and self.parent.scale > 0.6:
                self.parent.scale -= 0.1
            elif touch.button == 'scrollup':
                self.parent.scale += 0.1

        return super(CropImage, self).on_touch_down(touch)


class ImagesGalleryWin(BoxLayout):
    scatter_image = ObjectProperty()
    stacked_layout = ObjectProperty()
    scroll_view = ObjectProperty()
    image_name = ObjectProperty()
    target_coords_degrees = ObjectProperty()
    target_coords_fp = ObjectProperty()
    btn_shoot = ObjectProperty()
    btn_download = ObjectProperty()

    def updateImage(self, img_obj):
        """Update the displayed image"""

        self.scatter_image.img_obj = img_obj
        self.scatter_image.source = img_obj.path
        self.image_name.text = img_obj.name

    def updateTargetLocation(self, lat, lon):
        """Update the location pressed by the user."""

        minsec_lat, minsec_lon = decimal_to_minsec(lat, lon)

        self.target_coords_degrees.text = u'Lat: {}    Lon: {}'.format(minsec_lat, minsec_lon)
        self.target_coords_fp.text = u'Lat: {}    Lon: {}'.format(lat, lon)

    def setDownloadState(self, downloading):
        self.btn_download.state = 'down' if downloading else 'normal'

    def setCameraState(self, shooting):
        self.btn_shoot.state = 'down' if shooting else 'normal'

class ImageProcessingGui(BoxLayout):
    connect_label = ObjectProperty()
    images_gallery = ObjectProperty()
    crops_gallery = ObjectProperty()
    screen_manager = ObjectProperty()

    def __init__(self, **kwargs):
        super(ImageProcessingGui, self).__init__(**kwargs)
        self.app = App.get_running_app()


class ControllerGui(BoxLayout):
    connect_label = ObjectProperty()

    def __init__(self, **kwargs):
        super(ControllerGui, self).__init__(**kwargs)
        self.app = App.get_running_app()


class CropsGalleryWin(BoxLayout):
    scatter_image = ObjectProperty()
    stacked_layout = ObjectProperty()
    target_coords_degrees = ObjectProperty()
    target_coords_fp = ObjectProperty()
    qr_text = ObjectProperty()

    def updateCrop(self, crop_path, crop_yaw):
        """Update the displayed image"""

        self.scatter_image.source = crop_path
        self.scatter_image.parent.rotation = -crop_yaw

    def updateTargetLocation(self, lat, lon):
        minsec_lat, minsec_lon = decimal_to_minsec(lat, lon)

        self.target_coords_degrees.text = u'Lat: {}    Lon: {}'.format(minsec_lat, minsec_lon)
        self.target_coords_fp.text = u'Lat: {}    Lon: {}'.format(lat, lon)

    def updateQRText(self, text):
        self.qr_text.text = text


######################################################################
# Widgets for the Auto gui.
######################################################################
class LblTxt(BoxLayout):
    theTxt = ObjectProperty(None)


class Target(BoxLayout):
    target_image = ObjectProperty(None)
    targt_shape = ObjectProperty(None)
    bg_color = ObjectProperty(None)
    orient = ObjectProperty(None)
    char = ObjectProperty(None)
    char_color = ObjectProperty(None)
    latitude = ObjectProperty(None)
    latitude_deg = ObjectProperty(None)
    longitude = ObjectProperty(None)
    longitude_deg = ObjectProperty(None)

    def __init__(
        self,
        crop_path,
        target_shape,
        bg_color,
        orient,
        char,
        char_color,
        latitude,
        longitude,
        *params,
        **kwds
        ):
        super(Target, self).__init__(*params, **kwds)
        self.target_image.source = crop_path
        self.targt_shape.theTxt.text = target_shape
        self.bg_color.theTxt.text = bg_color
        self.orient.theTxt.text = str(orient)
        self.char.theTxt.text = char
        self.char_color.theTxt.text = char_color
        
        minsec_lat, minsec_lon = decimal_to_minsec(latitude, longitude)
        
        self.latitude.theTxt.text = '{0:.7f}'.format(latitude)
        self.latitude_deg.theTxt.text = minsec_lat
        self.longitude.theTxt.text = '{0:.7f}'.format(longitude)
        self.longitude_deg.theTxt.text = minsec_lon
        
class ADLCLayout(BoxLayout):
    images = ObjectProperty()
    targets = ObjectProperty()
    image_name = ObjectProperty()
    panel_orig = ObjectProperty()
    panel_mser = ObjectProperty()
    panel_shape = ObjectProperty()
    panel_letter = ObjectProperty()
    _panels = [panel_orig, panel_mser, panel_shape, panel_letter]


class AnalysisWin(GridLayout):
    panel_orig = ObjectProperty()
    panel_mser = ObjectProperty()
    panel_shape = ObjectProperty()
    panel_letter = ObjectProperty()

    def updateAnalysis(self, img_path, crops_df=None):

        self.panel_orig.image.updateImage(img_path)
        
        mser_rects = []
        shape_rects = []
        char_rects = []
        if crops_df is not None:
            mser_rects = [json.loads(coords) for coords in crops_df.index.values]
            
            shapes_df = crops_df[crops_df['shape']!=AUVSIcv.global_settings.SHAPE_LABELS[-1]]
            shape_rects = [json.loads(coords) for coords in shapes_df.index.values]
            
            chars_df = crops_df[crops_df['character'].notnull()]
            chars_df = chars_df[chars_df['character'] != AUVSIcv.global_settings.SHAPE_LABELS[-1]]            
            chars_df = chars_df[chars_df['character'] != AUVSIcv.global_settings.SHAPE_LABELS[-2]]
            char_rects = [json.loads(coords) for coords in chars_df.index.values]
            
            
        self.panel_mser.image.updateImage(img_path, mser_rects)
        self.panel_shape.image.updateImage(img_path, shape_rects)
        self.panel_letter.image.updateImage(img_path, char_rects)


class AutoPanel(BoxLayout):
    image = ObjectProperty()
    text = ObjectProperty()
    crop_color = ObjectProperty()


class AutoImage(Image):
    """A widget that allows drawing crops of the automatic system"""

    def __init__(self, *params, **kwds):

        super(AutoImage, self).__init__(*params, **kwds)
        self._group = None
        self._crops = []
        self.bind(size=self.drawCrops)

    def textureToPos(self, texture_x, texture_y, flip_y=True):
        offset_x = self.center[0] - self.norm_image_size[0] / 2
        offset_y = self.center[1] - self.norm_image_size[1] / 2

        scale_ratio = self.texture_size[0] / self.norm_image_size[0]

        #
        # Flip the y coord (the kivy pos coords start at bottom while the image's coords start at top).
        #
        if flip_y:
            texture_y = max(self.texture_size[1] - texture_y - 1, 0)

        x = texture_x / scale_ratio + offset_x
        y = texture_y / scale_ratio + offset_y

        return x, y

    def clearCrops(self):
        if self._group is None:
            return

        self.canvas.remove_group(self._group)
        self._group = None

    def updateImage(self, img_path, crops=[]):

        self.source = img_path
        self._crops = crops

        self.drawCrops()

    def drawCrops(self, *args, **kwds):

        self.clearCrops()
        if len(self._crops) == 0:
            return

        color = self.parent.crop_color

        with self.canvas:
            self._group = str(len(self._crops))
            Color(color[0], color[1], color[2], .75, mode='rgba', group=self._group)
            for coords in self._crops:
                start_x, start_y = self.textureToPos(*coords[:2])
                end_x, end_y = self.textureToPos(*coords[2:])

                Line(
                    rectangle=(start_x, start_y, end_x - start_x, end_y - start_y),
                    width=1.5,
                    group=self._group
                )


######################################################################
# Widgets for the Map gui.
######################################################################
class Map(Scatter):
    """Map class, based on scatter to allow zooming and moving."""

    do_rotation = False
    imgs = []
    margins = 50

    def __init__(self, *params, **kwds):

        super(Map, self).__init__(*params, **kwds)

        self._limits_set = False
        self._min_x = self._min_y = 1000000
        self._max_x = self._max_y = -1000000
        self.ned = None
        self.search_area_line = None
        self.planned_rout_line = None
        self.planned_grid_lines = []
        self.GPS_points = []
        self.GPS_points_on_canvas = []
        self.map_zero_point = None
        self._coords = None
        self._coords_route = None
        self.flight_boundary_line = None
        self.search_path_line = None
        self.obstacles = []
        self.CELL_HEIGHT = 18.2237 # 60 feet
        self.CELL_WIDTH  = 18.2237 # 60 feet
        self.grid_cell_height_on_list = self.feet_to_meters(int(App.get_running_app().config.get('MP', 'mp_grid_cell_height')))
        self.gris_cell_width_on_list = self.feet_to_meters(int(App.get_running_app().config.get('MP', 'mp_grid_cell_width')))

        with self.canvas:
            Color(1, 1, 1, 1, mode='rgba')

        # add : PicturesData(rowNum, colNum, cellSizeX, cellSizeY) that contains the grid and Graph
        self.picData = self.initPictureData(self.CELL_HEIGHT, self.CELL_WIDTH, "ShowGrid")


    def updateLimits(self, x, y):
        """Update the limits of the map for collision detection."""

        self._min_x = min(x, self._min_x)
        self._max_x = max(x, self._max_x)
        self._min_y = min(y, self._min_y)
        self._max_y = max(y, self._max_y)
        self._limits_set = True

    def getCoordsFromFile(self, file_name, with_radius = False):
        try:
            import os
            absPathFile = "C:/Users/adi/Desktop/"+str(file_name)
            os.path.abspath(absPathFile)
        except:
            print "in except reading from file"

        try:
            data_path = pkg_resources.resource_filename('AUVSIground', file_name)

            properties = []
            with open(data_path, 'rb') as f:
                for line in f:
                    if line.strip() == "":
                        continue  # Don't return empty lines
                    if not with_radius:
                        properties.append(
                            {key: float(val) for key, val in zip(('latitude', 'longitude'), (line.strip().split()))})
                    else:
                        properties.append(
                            {key: float(val) for key, val in zip(('latitude', 'longitude', 'radius'), (line.strip().split()))})
            return properties
        except:
            log.msg('Failed to load file')

    def getCoordsPlannedRoute(self):
        return self.getCoordsFromFile('resources/serch.waypoints')

    def getCoordsSearchArea(self):
        return self.getCoordsFromFile('resources/search_area.txt')

    def getObstaclesFromFile(self):
        return self.getCoordsFromFile('resources/obstacles.txt', with_radius=True)

    #def getCoords(self):
    #    try:
    #        data_path = pkg_resources.resource_filename('AUVSIground', 'resources/search_area.txt')
    #
    #        coords = []
    #        with open(data_path, 'rb') as f:
    #            for line in f:
    #                if line.strip() == "":
    #                    continue # Don't return empty lines
    #                coords.append(
    #                    {key: float(val) for key, val in zip(('latitude', 'longitude'), (line.strip().split()))})
    #        return coords
    #    except:
    #        log.msg('Failed to load search area data')



    def getRangeOfSearchArea(self):
        self._coords = self.getCoordsSearchArea()
        if self.ned is None:
            #
            # Map is drawn around the first search area point.
            #
            self.ned = AUVSIcv.NED.NED(self._coords[0]['latitude'], self._coords[0]['longitude'], 0)

        search_coords = []
        min_x = None
        max_x = None
        min_y = None
        max_y = None
        for coord in self._coords:
            y, x, h = self.ned.geodetic2ned([coord['latitude'], coord['longitude'], 0])

            if min_x is None:
                min_x = x
                max_x = x
                min_y = y
                max_y = y

            min_x = min(x, min_x)
            max_x = max(x, max_x)
            min_y = min(y, min_y)
            max_y = max(y, max_y)

        return min_x, max_x, min_y, max_y

    def setPlannedRout(self,coordsRout):
        """Draw the coordinates of the planned rout"""
        self._coordsRoute = coordsRout
        if self.ned is None:
            #
            # Map is drawn around the first search area point.
            #
            self.ned = AUVSIcv.NED.NED(coordsRout[0]['latitude'], coordsRout[0]['longitude'], 0)
        search_coords = []

        for coord in coordsRout:
            y, x, h = self.ned.geodetic2ned([coord['latitude'], coord['longitude'], 0])
            if (coord['latitude'] != 0) and (coord['longitude'] != 0):
                search_coords.append(x)
                search_coords.append(y)

        with self.canvas:
            Color(1, 1, 1, 1, mode='rgba')
            self.planned_rout_line = Line(points=search_coords, width=1.5, cap='none', joint='round', close=False)

        self._limits_set = True
    def setSearchArea(self, coords):
        """Draw the coordinates of the search area."""
        self._coords = coords
        if self.ned is None:
            #
            # Map is drawn around the first search area point.
            #
            self.ned = AUVSIcv.NED.NED(coords[0]['latitude'], coords[0]['longitude'], 0)
        search_coords = []
        for coord in coords:
            y, x, h = self.ned.geodetic2ned([coord['latitude'], coord['longitude'], 0])
            search_coords.append(x)
            search_coords.append(y)

            self.updateLimits(x, y)

        with self.canvas:
            Color(0, 0, 1, 1, mode='rgba')
            self.search_area_line = Line(points=search_coords, width=2, cap='none', joint='round', close=True)

        with self.canvas:
            Color(1, 0, 0, 1, mode='rgba')
            self.map_zero_point = Line(circle=(0, 0, 5), width=4)

    def setFlightBoundary(self, coords):
        boundary_coords = []
        for coord in coords:
            y, x, h = self.ned.geodetic2ned([coord['latitude'], coord['longitude'], 0])
            boundary_coords.append(x)
            boundary_coords.append(y)
            # print x, y, h

            self.updateLimits(x, y)

        with self.canvas:
            Color(1, 0, 0, 1, mode='rgba')
            self.flight_boundary_line = Line(points=boundary_coords, width=2, cap='none', joint='round', close=True)

    def setSearchPath(self, coords):
        path_coords = []
        for coord in coords:
            y, x, h = self.ned.geodetic2ned([coord['latitude'], coord['longitude'], 0])
            path_coords.append(x)
            path_coords.append(y)

            self.updateLimits(x, y)

        with self.canvas:
            Color(1, 1, 0, 1, mode='rgba')
            self.search_path_line = Line(points=path_coords, width=1, cap='none', joint='round', close=True)

    def setObstacles(self, obstacles):
        self.obstacles = []
        for obstacle in obstacles:
            lat, lon, h = self.ned.geodetic2ned([obstacle['latitude'], obstacle['longitude'], 0])
            R = self.feet_to_meters(float(obstacle['radius']))
            with self.canvas:
                Color(1, 0.5, 0, 1, mode='rgba')
                self.obstacles.append(Line(circle=(lon,  lat, R), width=2))

    def feet_to_meters(self, feet):
        return feet*0.3048


    def draw_undraw(self, instructions, color, on_off):
        # A function that adds or removes a drawn object from canvas.
        #   instructions - a set of instructions the canvas gets for drawing. For example - self.search_area_line
        #   Color - the color you want the shape to be drawn in RGBA. For example - (0,0,1,1) is blue.
        #   on_off - a boolean that tells the function to draw the shape or undraw it.
        if instructions is not None:
            if on_off:
                with self.canvas:
                    Color(*color, mode='rgba')
                self.canvas.add(instructions)
            else:
                self.canvas.remove(instructions)
        else:
            print "instructions == None"

    def draw_planned_rout(self, on_off):
        self.draw_undraw(self.planned_rout_line, (1, 1, 1, 1), on_off)

    def draw_search_area(self, on_off):
        self.draw_undraw(self.search_area_line, (0, 0, 1, 1), on_off)

    def draw_grid(self, on_off):
        # check if there is a need to change grid

        grid_cell_height_on_list_new = self.feet_to_meters(int(App.get_running_app().config.get('MP', 'mp_grid_cell_height')))
        check_diff_width_new = self.feet_to_meters(int(App.get_running_app().config.get('MP', 'mp_grid_cell_width')))
        check_diff_height = self.grid_cell_height_on_list != grid_cell_height_on_list_new
        check_diff_width = self.gris_cell_width_on_list != check_diff_width_new

        if on_off is True:
            # need to remove ines from list
            for curr_Line in self.planned_grid_lines:
                self.draw_undraw(curr_Line, (0, 1, 0, 1), True)
            if check_diff_height or check_diff_width:
                self.set_grid()
        else:
            for curr_Line in self.planned_grid_lines:
                self.draw_undraw(curr_Line, (0, 1, 0, 1), False)
            if check_diff_height or check_diff_width:
                self.set_grid()
                for curr_Line in self.planned_grid_lines:
                    self.draw_undraw(curr_Line, (0, 1, 0, 1), False)

        #for curr_Line in self.planned_grid_lines:
        #    self.draw_undraw(curr_Line, (0, 1, 0, 1), on_off)

        self.grid_cell_height_on_list = self.feet_to_meters(
            int(App.get_running_app().config.get('MP', 'mp_grid_cell_height')))
        self.gris_cell_width_on_list = self.feet_to_meters(
            int(App.get_running_app().config.get('MP', 'mp_grid_cell_width')))

    def draw_flight_boundary(self, on_off):
        self.draw_undraw(self.flight_boundary_line, (1, 0, 0, 1), on_off)

    def draw_search_path(self, on_off):
        self.draw_undraw(self.search_path_line, (1, 1, 0, 1), on_off)

    def collide_point(self, x, y):
        """Check if the user is touching the map."""

        stencil = self.parent.parent

        #
        # Check if inside the encapsulating stencil.
        #
        if not stencil.collide_point(*self.to_window(x, y)):
            return False

        #
        # If empty, use scatter collide.
        #
        if not self._limits_set:
            return super(Map, self).collide_point(x, y)

        #
        # Check if the press is inside the map (takes into account negative values).
        #
        x, y = self.to_local(x, y)
        x_collide = self._min_x - self.margins < x < self._max_x + self.margins
        y_collide = self._min_y - self.margins < y < self._max_y + self.margins

        return x_collide and y_collide

    def addImage(self, img, toRedraw = True):
        """Add a new image to the map"""

        # self.canvas.clear()
        if self.ned is None:
            #
            # Map is drawn around first image.
            #
            print 'Setting first image'
            self.ned = AUVSIcv.NED.NED(img.latitude, img.longitude, 0)

        #
        # Calculate the coordinates of the image (corners of quad)
        #
        projections = img.calculateQuad(self.ned)
        points = tuple(projections.T[...,:2].flatten())

        #
        # Calculate the new limits of the map on the canvas
        #
        self.updateLimits(min(points[::2]), min(points[1::2]))
        self.updateLimits(max(points[::2]), max(points[1::2]))

        minXImage = min(points[::2])
        maxXImage = max(points[::2])
        minYImage = min(points[1::2])
        maxYImage = max(points[1::2])

        newProjections = self.picData.addPicture(img, Area(minXImage,maxXImage, minYImage, maxYImage))
        if newProjections is not None:
            points = tuple(newProjections.T[..., :2].flatten())

        #
        # Add the new image to the canvas.
        #
        with self.canvas:
            Color(1, 1, 1, 1, mode='rgba')
            Quad(source=img.path, points=points)

        self.add_GPS_point(img.latitude, img.longitude)
        if toRedraw is True:
            self.redrawLinesOfButtons() #withoutGPSpoints

    def redrawLinesOfButtons(self):
        # search area
        if App.get_running_app().get_button_state('search_area'):
            self.draw_search_area(False)
            self.draw_search_area(True)
        # flight boundary
        if App.get_running_app().get_button_state('flight_boundary'):
            self.draw_flight_boundary(False)
            self.draw_flight_boundary(True)
        # search path
        if App.get_running_app().get_button_state('search_path'):
            self.draw_search_path(False)
            self.draw_search_path(True)
        # grid
        if App.get_running_app().get_button_state('grid'):
            self.draw_grid(False)
            self.draw_grid(True)
        # GPS points
        if App.get_running_app().get_button_state('points_gps'):
            self.draw_GPS_points(False)
            self.draw_GPS_points(True)
        # Obstacles
        if App.get_running_app().get_button_state('obstacles'):
            self.draw_obstacles(False)
            self.draw_obstacles(True)

    def add_GPS_point(self, latitude, longitude):
        y, x, h = self.ned.geodetic2ned([latitude, longitude, 0])
        self.GPS_points.append(Line(circle=(x, y, 0), width=2))

    def draw_GPS_points(self,on_off):
        max_length = int(App.get_running_app().config.get('MP', 'mp_gps'))
        if on_off is True: #draw
            if len(self.GPS_points) < max_length:
                self.GPS_points_on_canvas = list(self.GPS_points)
            else:
                self.GPS_points_on_canvas = list(self.GPS_points[-max_length:])

            for curr_Line in self.GPS_points_on_canvas:
                self.draw_undraw(curr_Line, (0, 1, 1, 1), on_off)
        else:              #undraw
            for curr_Line in self.GPS_points_on_canvas:
                self.draw_undraw(curr_Line, (0, 1, 1, 1), on_off)
            self.GPS_points_on_canvas = []

    def draw_obstacles(self, on_off):
        for curr_Line in self.obstacles:
            self.draw_undraw(curr_Line, (1, 0.5, 0, 1), on_off)

    def set_grid(self):

        if len(self.planned_grid_lines) > 0:
            # remove lines from list and canvas
            self.planned_grid_lines = []

        cell_height = self.feet_to_meters(int(App.get_running_app().config.get('MP', 'mp_grid_cell_height')))
        cell_width = self.feet_to_meters(int(App.get_running_app().config.get('MP', 'mp_grid_cell_width')))

        min_x, max_x, min_y, max_y = self.getRangeOfSearchArea()
        x_diff = max_x - min_x
        y_diff = max_y - min_y
        num_of_cols = long(round(x_diff / cell_width) + 1)
        num_of_rows = long(round(y_diff / cell_height) + 1)

        """Draw the grid lines ."""

        for index in range(num_of_rows):
            y = min_y + (index * cell_height)
            pointsRows = []

            pointsRows.append(min_x)
            pointsRows.append(y)

            pointsRows.append(max_x)
            pointsRows.append(y)

            with self.canvas:
                Color(0, 1, 0, 1, mode='rgba')
                self.planned_grid_lines.append(Line(points=pointsRows, width=1, cap='none', joint='round', close=True))

        for index in range(num_of_cols):
            x = min_x + (index * cell_width)
            pointsCols = []

            pointsCols.append(x)
            pointsCols.append(min_y)

            pointsCols.append(x)
            pointsCols.append(max_y)
            with self.canvas:
                Color(0, 1, 0, 1, mode='rgba')
                self.planned_grid_lines.append(Line(points=pointsCols, width=1, cap='none', joint='round', close=True))

    def on_touch_down(self, touch):

            #
            # Check if mouse event
        #
        if touch.device == 'mouse':

            if touch.button in ('scrolldown', 'scrollup'):
                #
                # Check if the scroll wheel is used
                #
                if touch.button == 'scrolldown' and self.scale > 0.3:
                    self.scale -= 0.1
                    #print "scale = ", self.scale
                elif touch.button == 'scrollup':
                    self.scale += 0.1
                    #print "scale = ", self.scale

                return True

            elif touch.button == 'right':
                #
                # Note: there is no need to grab the touch
                # as this is done by the underlying scatter.
                #
                touch.ud['action'] = MapCoordsAction(self, touch)

        return super(Map, self).on_touch_down(touch)

    def on_touch_move(self, touch):

        if touch.device == 'mouse':
            if touch.button == 'left':
                if touch.ud.get('action') is not None:
                    touch.ud['action'].on_touch_move(touch)

                return super(Map, self).on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.ud.get('action') is not None:
            touch.ud['action'].on_touch_up(touch)
            touch.ud['action'] = None

        return super(Map, self).on_touch_up(touch)

    def initPictureData(self, cellHight, cellWidth, showGridOnMap = None, setMaxRows = None, setMaxCols = None, isStitchingON = False):
        min_x, max_x, min_y, max_y = self.getRangeOfSearchArea()

        x_diff = max_x - min_x
        y_diff = max_y - min_y
        numOfRows = long(round(x_diff / cellWidth) + 1)
        numOfCols = long(round(y_diff / cellHight) + 1)

        if setMaxRows is not None:
            numOfRows = setMaxRows
        if setMaxCols is not None:
            numOfCols = setMaxCols

        picData = PicturesData(numOfRows, numOfCols, cellHight, cellWidth, isStitchingON)

        return picData


class MapGui(BoxLayout):
    map_widget = ObjectProperty()
    tc_degrees = ObjectProperty()
    tc_fp = ObjectProperty()

    def updateLocationOnMap(self, lat, lon):
        """Update the location pressed by the user."""

        minsec_lat, minsec_lon = decimal_to_minsec(lat, lon)

        self.tc_degrees.text = u'Lat: {}    Lon: {}'.format(minsec_lat, minsec_lon)
        self.tc_fp.text = u'Lat: {}    Lon: {}'.format(lat, lon)
        
        
class TargetProperties(BoxLayout):
    target_type = ObjectProperty()
    shape = ObjectProperty()
    shape_color = ObjectProperty()
    text = ObjectProperty()
    text_color = ObjectProperty()
    target_orientation = ObjectProperty()
    lat = ObjectProperty()
    lon = ObjectProperty()
    crop_name = ObjectProperty()
    crop_path = ObjectProperty()
    desc = ObjectProperty()

    def updateTarget(self, target):
        lat, lon = decimal_to_minsec(target.lat, target.lon)
        self.target_type.text = target.type
        self.shape.text = target.shape
        self.shape_color.text = target.shape_color
        self.text.text = target.text
        self.text_color.text = target.text_color
        self.target_orientation.text = str(target.orientation)
        self.desc.text = target.desc
        self.lat.text = '{minsec_lat} ({dec_lat})'.format(minsec_lat=lat, dec_lat=str(target.lat))
        self.lon.text = '{minsec_lon} ({dec_lon})'.format(minsec_lon=lon, dec_lon=str(target.lon))
        self.crop_name.text = target.crop_name
        self.crop_path.text = target.crop_path

        self.target_type.readonly = target.committed
        self.shape.readonly = target.committed
        self.shape_color.readonly = target.committed
        self.text.readonly = target.committed
        self.text_color.readonly = target.committed
        self.target_orientation.readonly = target.committed
        self.desc.readonly = target.committed

    def saveToTarget(self, target):
        if target.committed:
            return

        target.type = self.target_type.text
        target.shape = self.shape.text
        target.shape_color = self.shape_color.text
        target.text = self.text.text
        target.text_color = self.text_color.text
        target.orientation = self.target_orientation.text
        target.desc = self.desc.text

class TargetsLayout(BoxLayout):
    crops = ObjectProperty()
    targets = ObjectProperty()
    committed_targets = ObjectProperty()
    selected_crop = ObjectProperty()
    selected_target = ObjectProperty()
    props = ObjectProperty()

    def updateCrop(self, crop):
        """Update the displayed image"""

        self.selected_crop.source = crop.path
        self.selected_crop.parent.rotation = -crop.yaw

    def updateTarget(self, target):
        """Update the displayed image"""

        self.selected_target.source = target.crop_path
        self.selected_target.parent.rotation = -target.yaw

    def updateTargetLocation(self, lat, lon):
        minsec_lat, minsec_lon = decimal_to_minsec(lat, lon)

        #self.target_coords_degrees.text = u'Lat: {}    Lon: {}'.format(minsec_lat, minsec_lon)
        #self.target_coords_fp.text = u'Lat: {}    Lon: {}'.format(lat, lon)

# Taken from https://github.com/kivy/kivy/wiki/Editable-ComboBox
class ComboEdit(TextInput):

    options = ListProperty(('', ))

    def __init__(self, **kw):
        ddn = self.drop_down = DropDown()
        ddn.bind(on_select=self.on_select)
        super(ComboEdit, self).__init__(**kw)

    def on_options(self, instance, value):
        ddn = self.drop_down
        ddn.clear_widgets()
        for widg in value:
            widg.bind(on_release=lambda btn: ddn.select(btn.text))
            ddn.add_widget(widg)

    def on_select(self, *args):
        if not self.readonly:
            self.text = args[1]

    def on_touch_up(self, touch):
        if touch.grab_current == self:
            self.drop_down.open(self)
        return super(ComboEdit, self).on_touch_up(touch)
