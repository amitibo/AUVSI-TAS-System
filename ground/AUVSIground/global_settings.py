from datetime import datetime
import os

BASE_TIMESTAMP = '%Y_%m_%d_%H_%M_%S_%f'

#
# Paths and Folders
#
AUVSI_BASE_FOLDER = os.path.expanduser('~/.auvsi_ground')
IMAGES_FOLDER = os.path.join(AUVSI_BASE_FOLDER, 'images')
CROPS_FOLDER = os.path.join(AUVSI_BASE_FOLDER, 'crops')
THUMBNAILS_FOLDER = os.path.join(AUVSI_BASE_FOLDER, 'thumbs')
FLIGHTDATA_FOLDER = os.path.join(AUVSI_BASE_FOLDER, 'flight_data')
TARGETS_FOLDER = os.path.join(AUVSI_BASE_FOLDER, 'targets')
CTRL_IMAGES_FOLDER = os.path.join(AUVSI_BASE_FOLDER, 'controller_images')
CTRL_CROPS_FOLDER = os.path.join(AUVSI_BASE_FOLDER, 'controller_crops')
CTRL_FLIGHTDATA_FOLDER = os.path.join(AUVSI_BASE_FOLDER, 'controller_flight_data')

AUVSI_AUTO_BASE_FOLDER = os.path.expanduser('~/.auvsi_auto')
AUTO_FOLDER = os.path.join(AUVSI_AUTO_BASE_FOLDER, 'auto')
CROPS_AUTO_FOLDER = os.path.join(AUVSI_AUTO_BASE_FOLDER, 'crops_auto')

#
# Data Types (airborne and ground station data types should match)
#
RESIZED_IMAGE = 'resized_img'
MANUAL_CROP = 'man_crop'
AUTO_CROP = 'auto_crop'
CROP_REQUESTS = 'crop_requests'
AUTO_ANALYSIS = 'auto_analysis'
TARGET_DATA = 'target_data'
FLIGHT_DATA = 'flight_data'
STATE = 'state'
STATE_DOWNLOAD = 'download'
STATE_SHOOT = 'shoot'
STATE_ON = 'on'
STATE_OFF = 'off'
TARGET_AUTO = 'auto'
TARGET_MANUAL = 'manual'
TARGET_INFO = 'target_info'

#
# Ground data types
#
SYNC_LIST = 'sync'
SYNC_LIST_IMAGES = 'images'
SYNC_LIST_CROPS = 'crops'
SYNC_QUEUE = 'queue'
SYNC_IMAGE = 'image'
SYNC_CROP = 'crop'
SYNC_TARGET = 'target'

#
# ROLES
#
PRIMARY = 'primary'
SECONDARY = 'secondary'
CONTROLLER = 'controller'
SUB_TAG = b'auvsi'

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
ZMQ_PRIMARY_GS_CONTROLLER_PORT = 8811

#
# Ports for communicating between ADLC workers and main AUTO process.
#
ZMQ_AUTO_WORKER_PUSH = 8900
ZMQ_AUTO_WORKER_PULL = 8901

#
# Constants
#
MINIMAL_CROP_SIZE = 5
MAX_AUTO_CROPS_PER_IMAGE = 20
IMAGE_QUEUE_COUNT = 2
IMAGE_QUEUE_LOOK_AHEAD = 2

#
# AUTO gui
#
AUTO_IMAGE_DB_PATH = os.path.join(AUVSI_AUTO_BASE_FOLDER, 'image_db.csv')
AUTO_CROPS_DB_PATH = os.path.join(AUVSI_AUTO_BASE_FOLDER, 'crops_db.csv')

#
# The following variable sets the distance below which automatic
# targets are averaged.
#
SAME_TARGET_MAX_DISTANCE = 0.0003
AUTO_TABLES_SAVE_PERIOD = 5
