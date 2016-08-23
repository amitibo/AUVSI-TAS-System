import os
import warnings
from datetime import datetime

BASE_TIMESTAMP = '%Y_%m_%d_%H_%M_%S_%f'

#
# Paths and Folders
#
#AUVSI_BASE_FOLDER = os.path.join(os.path.expanduser('~/.auvsi_airborne'), datetime.now().strftime(BASE_TIMESTAMP))
AUVSI_BASE_FOLDER = os.path.expanduser('~/.auvsi_airborne')
IMAGES_FOLDER = os.path.join(AUVSI_BASE_FOLDER, 'images')
RENAMED_IMAGES_FOLDER = os.path.join(AUVSI_BASE_FOLDER, 'renamed_images')
RESIZED_IMAGES_FOLDER = os.path.join(AUVSI_BASE_FOLDER, 'resized_images')
CROPS_FOLDER = os.path.join(AUVSI_BASE_FOLDER, 'crops')
RESIZED_PREFIX = 'resized_'
FLIGHT_DATA_FOLDER = os.path.join(AUVSI_BASE_FOLDER, 'flight_data')
DB_FOLDER = os.path.join(AUVSI_BASE_FOLDER, 'db')
DB_PATH = os.path.join(DB_FOLDER, 'auvsi.db')

#
# Data Types (airborne and ground station data types should match)
#
RESIZED_IMAGE = 'resized_img'
MANUAL_CROP = 'man_crop'
AUTO_CROP = 'auto_crop'
FLIGHT_DATA = 'flight_data'
AUTO_ANALYSIS = 'auto_analysis'
STATE = 'state'
STATE_DOWNLOAD = 'download'
STATE_SHOOT = 'shoot'
STATE_ON = 'on'
STATE_OFF = 'off'

#
# Camera data
#
BASE_ZOOM = 0

#
# Default ports. (airborne and ground station values should match)
#
CAMERA_CTL_PORT = 8555
ZMQ_CAMERA_NOTICE_PORT = 8800
ZMQ_CAMERA_FILES_PORT = 8801

#
# Ports for communicating between GS stations.
#
ZMQ_PRIMARY_GS_PORT = 8810

#
# Constants
#
MINIMAL_FUL_CROP_SIZE = 20
SEARCH_AREA_BUFFER_DEG = 0.0
