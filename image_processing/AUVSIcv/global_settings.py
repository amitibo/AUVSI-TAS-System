from __future__ import division
import numpy as np
import glob
import os


#
# TARGET SIZE RANGES
#
NORMAL_TARGET_SIZE_RANGE = (0.6, 2.4)
QR_TARGET_SIZE_RANGE = (0.9, 1.2)

#
# These values are used for blending targets into images.
# POISSON_INTENSITY_RATIO - Ratio by which to scale up the RGB values before applying possion noise.
# EMPIRICAL_IMAGE_INTENSITY - Some 'empirical' value that is supposed to be a normal intensity of an image.
#
EMPIRICAL_IMAGE_INTENSITY = 30
POISSON_INTENSITY_RATIO = 10

#
# TARGET DETECTION PARAMETERS
#
MSER_MEDIAN_BLUR = 25
CROP_MARGINS = 0
CROPS_SIMILARITY_THRESHOLD = 20
CROPS_RATIO_THRESHOLD = 1.7
PATCH_SIZE = (220, 220)
RANDOM_PATCH_SIZE_RANGE = (15, 70)
CLASSIFIER_PATCH_SIZE = (32, 32)
LETTER_PATCH_SIZE = (32, 32)
LETTER_MARGIN = 2
PATCH_COORDS_NOISE = 0.8
USE_CV2_KMEANS = True

#
# Letter parameters.
#
import pkg_resources
FONTS = glob.glob(os.path.join(pkg_resources.resource_filename('AUVSIcv', 'resources/fonts'), '*.ttf'))

EXTRA_SET = False
if EXTRA_SET:
    LETTERS = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
    ROTATABLE_LETTERS = '12345679ABCDEFGJKLMPQRTUVWYabcdefghijkmnpqrtuvwy'
    HALF_ROTATABLE_LETTERS = '8HINSXZsxz'
else:
    LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    ROTATABLE_LETTERS = 'ABCDEFGJKLMPQRTUVWY'
    HALF_ROTATABLE_LETTERS = 'HINSXZ'

LETTER_CONFIDENCE_THRESHOLD = 0.95

#
# ADLC
# ----
# Possible labels
#
SHAPE_LABELS = (
    'Circle',
    'Half Circle',
    'Quarter Circle',
    'Rectangle',
    'Trapezoid',
    'Triangle',
    'Cross',
    'Pentagon',
    'Hexagon',
    'Heptagon',
    'Octagon',
    'Star',
    'QRcode',
    'no target'
)
LETTER_LABELS = list(LETTERS) + ['no target', 'rotated letter']

ADLC_SEND_FULLSIZE = True

#
# Amit: Hard coded intrinsic matrix of the Sony Camera at 16mm.
# TODO: This should be removed, and be set by the flight data.
#
K = np.array(
    (
        (8000., 0, 3006.01964096616),
        (0, 8000., 1999.15606078653),
        (0, 0, 1)
    )
)

FX_RESIZE_RATIO = 1616.0/6000.0
FY_RESIZE_RATIO = 1080.0/4000.0
IMAGE_RESIZE_MATRIX = np.array(((FX_RESIZE_RATIO, 0, 0), (0, FY_RESIZE_RATIO, 0), (0, 0, 1)))
resized_K = np.dot(IMAGE_RESIZE_MATRIX, K)
MAP_SIZE = 100
MAP_RESIZE_RATIO = MAP_SIZE/6000.0
map_K = np.dot(np.diag((MAP_RESIZE_RATIO, MAP_RESIZE_RATIO, 1)), K)
