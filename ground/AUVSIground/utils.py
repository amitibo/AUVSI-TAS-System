from __future__ import division
import numpy as np
import glob
import json
import os

__author__ = 'Ori'

__all__ = (
    'decimal_to_minsec',
    'FileSelector',
    'loadFlightData',
    'loadPHFlightData',
    'calculateOrientation'
)


def decimal_to_minsec(lat, lon):
    """
    Converts latitude and longitude in decimal representation to minute-second
    representation
    :param lat: the number in decimal (can be ether string or float)
    :param lon: the number in decimal (can be ether string or float)
    :return: string
    """
    res = list()
    for num, pol, width in zip((lat, lon), (('N', 'S'), ('E', 'W')), (2, 3)):
        num = float(num)

        pol_index = 0
        if num < 0:
            num = -num
            pol_index = 1

        deg = int(num)
        residue = num - deg

        minutes = residue*60
        residue = minutes - int(minutes)
        minutes = int(minutes)

        seconds = residue*60

        degmin = ('{pol}{deg:0' + str(width) + '} {minutes:02} {sec:06,.3f}').format(
            deg=deg,
            minutes=minutes,
            sec=seconds,
            pol=pol[pol_index]
        )

        res.append(degmin)

    return res


class FileSelector(object):
    '''
    A class that creates a list of the files in a given path.
    returns the next file or previous file in the list
    and update the given file to be set as the current file for future calls
    '''
    def __init__(self, dir_path, extension):
        self.dir_path = dir_path
        self.extension = extension
        self.current_file = None

    def _get_file_list(self):
        files = os.listdir(self.dir_path)
        return sorted([f for f in files if f.endswith('.' + self.extension)])

    def next_file(self):
        file_list = self._get_file_list()

        if not self.current_file:
            try:
                self.current_file = file_list[0]
            except IndexError:
                raise NoFiles()

            return self.current_file

        current_file_index = file_list.index(self.current_file)
        try:
            self.current_file = file_list[current_file_index + 1]
        except IndexError:
            pass
        return self.current_file

    def prev_file(self):
        file_list = self._get_file_list()

        if not self.current_file:
            try:
                self.current_file = file_list[0]
            except IndexError:
                raise NoFiles()

            return self.current_file

        current_file_index = file_list.index(self.current_file)

        self.current_file = file_list[max(current_file_index - 1, 0)]
        return self.current_file


def loadFlightData(flightdata_path, pattern='resized_*.json'):
    paths = glob.glob(os.path.join(flightdata_path, pattern))
    paths = sorted(paths)

    lat, lon, alt = [], [], []
    ph_roll, ph_pitch, ph_yaw = [], [], []
    vn_roll, vn_pitch, vn_yaw = [], [], []
    for path in paths:
        with open(path, 'r') as f:
            d = json.load(f)
            lat.append(d['lat'])
            lon.append(d['lon'])
            alt.append(d['relative_alt'])
            ph_roll.append(d['all']['PixHawk']['roll'])
            ph_pitch.append(d['all']['PixHawk']['pitch'])
            ph_yaw.append(d['all']['PixHawk']['yaw'])
            if "VectorNav" in d['srcs']:
                vn_roll.append(d['all']['VectorNav']['roll'])
                vn_pitch.append(d['all']['VectorNav']['pitch'])
                vn_yaw.append(d['all']['VectorNav']['yaw'])
            else:
                vn_roll.append(np.NaN)
                vn_pitch.append(np.NaN)
                vn_yaw.append(np.NaN)

    dd = {
        'lat': np.array(lat)*1e-7,
        'lon': np.array(lon)*1e-7,
        'alt': np.array(alt)*1e-3,
        'ph_roll': ph_roll, 'ph_pitch': ph_pitch, 'ph_yaw': ph_yaw,
        'vn_roll': vn_roll, 'vn_pitch': vn_pitch, 'vn_yaw': vn_yaw,
    }

    import pandas as pd
    df = pd.DataFrame(dd)

    return df


def loadPHFlightData(flightdata_path, pattern='*.json'):
    paths = glob.glob(os.path.join(flightdata_path, pattern))
    paths = sorted(paths)

    lat, lon, alt = [], [], []
    ph_roll, ph_pitch, ph_yaw = [], [], []
    for path in paths:
        with open(path, 'r') as f:
            d = json.load(f)
            lat.append(d['lat'])
            lon.append(d['lon'])
            alt.append(d['relative_alt'])
            ph_roll.append(d['roll'])
            ph_pitch.append(d['pitch'])
            ph_yaw.append(d['yaw'])

    dd = {
        'lat': np.array(lat)*1e-7,
        'lon': np.array(lon)*1e-7,
        'alt': np.array(alt)*1e-3,
        'ph_roll': ph_roll, 'ph_pitch': ph_pitch, 'ph_yaw': ph_yaw,
    }

    import pandas as pd
    df = pd.DataFrame(dd)

    return df


def calculateOrientation(yaw):
    yaw = (yaw + 720) % 360
    if yaw >= 360 - 22.5 or yaw < 22.5:
        return 'N'
    elif yaw < 45 + 22.5:
        return 'NE'
    elif yaw < 90 + 22.5:
        return 'E'
    elif yaw < 135 + 22.5:
        return 'SE'
    elif yaw < 180 + 22.5:
        return 'S'
    elif yaw < 225 + 22.5:
        return 'SW'
    elif yaw < 270 + 22.5:
        return 'W'
    else:
        return 'NW'

