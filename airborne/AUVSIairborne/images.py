from __future__ import division
from twisted.internet import threads
from twisted.python import log
import multiprocessing as mp
import PixHawk as PH
from datetime import datetime
import global_settings as gs
import numpy as np
import AUVSIcv
import json
import time
import cv2
import os
import traceback
import pexif

pool = None
RESIZE_USING_EXIF_PREVIEW = 1

def tagRatio(tag):
    ratio = tag.values[0].num/tag.values[0].den
    return ratio

def tagValue(tag):
    return tag.values[0]

def mergeFlightData(fds):
    flight_data = {
        'yaw': 0,
        'pitch': 0,
        'roll': 0,
        'src_att': None,
        'hdg': 0,
        'src_hdg': None,
        'lat': 0,
        'lon': 0,
        'relative_alt': 0,
        'src_gps': None,
        'cog': 0,
        'src_cog': None
    }

    groups = {
        'src_att': [ 'yaw', 'pitch', 'roll' ],
        'src_hdg': [ 'hdg' ],
        'src_gps': [ 'lat', 'lon', 'relative_alt' ],
        'src_cog': [ 'cog' ]
    }

    # Create an empty all data array
    all_data = {}

    # Copy the timestamp from the first data
    flight_data['fd_timestamp'] = fds[0]['fd_timestamp']
    srcs = []

    for fd in fds:

        # Copy the data to the all data dictionary
        all_data[fd['src']] = fd

        for selector in groups:
            # Check if the group is missing in the global data but exists in this data
            if flight_data[selector] is None and fd[selector] is not None:
                # Copy the keys' values
                for key in groups[selector]:
                    flight_data[key] = fd[key]

                # Copy the source selector
                flight_data[selector] = fd[selector]

        if 'src' in fd:
            srcs.append(fd['src'])

    flight_data['srcs'] = srcs;
    flight_data['all'] = all_data

    return flight_data

def getFlightData(time, K, vn=None):
    """Get the Pixhawk flightdata corresponding to a timestamp (of an image)."""

    fds = []

    #
    # Get the closest time stamp and save it with the image.
    #
    if vn is not None:
        view = vn.getView(time)

        if view is not None:
            fds.append(view.dict)

    fds.append(PH.queryPHdata(time.strftime(gs.BASE_TIMESTAMP)))

    flight_data = mergeFlightData(fds)
    flight_data['K'] = K.tolist()
    flight_data['resized_K'] = True
    flight_data['timestamp'] = time.strftime(gs.BASE_TIMESTAMP)

    if len(flight_data['srcs']) > 0:
        srcs = ', '.join(flight_data['srcs'])
    else:
        srcs = 'Unknown'

    log.msg('Got flight data from {srcs}'.format(srcs=srcs))

    return flight_data


def processImg(img_path, current_time, img_time, vn=None):
    """
    Do all image processing actions. Should be called on a separate process to allow mutli processesors.
    Currently does only resizing.
    """

    #
    # Load the image
    #
    log.msg('Loading new image {img}'.format(img=img_path))

    img = None
    jpeg_preview = None
    use_preview = 0

    if RESIZE_USING_EXIF_PREVIEW:
        try:
            jpeg_orig = pexif.JpegFile.fromFile(img_path)

            if jpeg_orig.app2 is not None and len(jpeg_orig.app2.primary.preview) > 0:
                jpeg_preview = pexif.JpegFile.fromString(jpeg_orig.app2.primary.preview[0])
                #jpeg_preview.import_exif(jpeg_orig.exif)

                use_preview = 1
            else:
                log.msg('No EXIF preview found, switching to OpenCV')

        except:
            use_preview = 0
            log.msg('WARNING: Using EXIF preview failed, switching to OpenCV')
            log.err(traceback.format_exc())

    current_timestamp = current_time.strftime(gs.BASE_TIMESTAMP)

    if not use_preview:
        img = AUVSIcv.Image(img_path, timestamp=current_timestamp, K=AUVSIcv.global_settings.K)

    #
    # Rename it with time stamp.
    #
    new_img_path = os.path.join(gs.RENAMED_IMAGES_FOLDER, current_timestamp+'.jpg')

    log.msg('Renaming {old} to {new}'.format(old=img_path, new=new_img_path))
    os.rename(img_path, new_img_path)

    #
    # Resize the image.
    #
    log.msg('Resizing new image {img}'.format(img=new_img_path))

    filename = '{prefix}{path}'.format(prefix=gs.RESIZED_PREFIX, path=os.path.split(new_img_path)[1])
    resized_img_path = os.path.join(gs.RESIZED_IMAGES_FOLDER, filename)

    if not use_preview:
        resized_img = cv2.resize(img.img, (0,0), fx=AUVSIcv.global_settings.FX_RESIZE_RATIO, fy=AUVSIcv.global_settings.FY_RESIZE_RATIO)
        cv2.imwrite(resized_img_path, resized_img)
    else:
        jpeg_preview.writeFile(resized_img_path)

    #
    # Find the corresponding flight data.
    #
    flight_data = getFlightData(img_time, AUVSIcv.global_settings.resized_K, vn)
    flight_data_path = os.path.splitext(resized_img_path)[0]+'.json'
    with open(flight_data_path, 'wb') as f:
        json.dump(flight_data, f)
    log.msg('Saving flight data to path {path}'.format(path=os.path.split(flight_data_path)[-1]))
    #resized_img_path="unnamed"
    #flight_data={}

    return new_img_path, resized_img_path, flight_data


def handleNewCrop(img_name, coords):
    """Handle a request for a crop."""

    #
    # Get the original size image.
    #
    original_img_name = img_name[len(gs.RESIZED_PREFIX):]
    original_img_path = os.path.join(gs.RENAMED_IMAGES_FOLDER, original_img_name)

    if not os.path.isfile(original_img_path):
        raise Exception("Unknown image file: {img_name}".format(img_name=original_img_path))

    #
    # Load the image.
    #
    img = cv2.imread(original_img_path)

    #
    # Scale the coords
    #
    scaled_coords = [
        coords[0]/AUVSIcv.global_settings.FX_RESIZE_RATIO,
        coords[1]/AUVSIcv.global_settings.FY_RESIZE_RATIO,
        coords[2]/AUVSIcv.global_settings.FX_RESIZE_RATIO,
        coords[3]/AUVSIcv.global_settings.FY_RESIZE_RATIO,
    ]
    coords = [int(round(c)) for c in scaled_coords]

    #
    # Check the coords.
    #
    h, w, _ = img.shape
    coords[0] = min(max(coords[0], 0), w)
    coords[1] = min(max(coords[1], 0), h)
    coords[2] = min(max(coords[2], 0), w)
    coords[3] = min(max(coords[3], 0), h)

    if coords[3]-coords[1] < gs.MINIMAL_FUL_CROP_SIZE or coords[2]-coords[0] < gs.MINIMAL_FUL_CROP_SIZE:
        raise Exception("Illegal coords (size too small) {coords}".format(coords=coords))

    #
    # Create the crop
    #
    log.msg("Crop {img}, of size {shape} in coord {coords}".format(img=original_img_name, shape=img.shape, coords=coords))
    return img[coords[1]:coords[3], coords[0]:coords[2], ...]


def initIM():
    global pool

    #pool = mp.Pool(2)

    if not os.path.exists(gs.RESIZED_IMAGES_FOLDER):
        os.makedirs(gs.RESIZED_IMAGES_FOLDER)
        os.makedirs(gs.RENAMED_IMAGES_FOLDER)
        os.makedirs(gs.CROPS_FOLDER)
