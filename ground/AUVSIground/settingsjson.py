import json
import global_settings as gs
network_json = json.dumps(
    [
        {'type': 'title',
         'title': 'Airborne Server'},
        {'type': 'string',
         'title': 'IP',
         'desc': 'IP address or HOSTNAME of airborne server',
         'section': 'Network',
         'key': 'ip'},
        {'type': 'options',
         'title': 'role',
         'desc': 'Role of the station (primary/secondary)',
         'section': 'Network',
         'key': 'role',
         'options': [gs.PRIMARY, gs.SECONDARY]},
        {'type': 'string',
         'title': 'IP_CONTROLLER',
         'desc': 'IP address or HOSTNAME of controller station (used only by primary and seconday stations)',
         'section': 'Network',
         'key': 'ip_controller'}
    ]
)

camera_json = json.dumps(
    [
        {'type': 'title',
         'title': 'Camera Settings'},
        {'type': 'numeric',
         'title': 'ISO',
         'desc': 'ISO settings of camera',
         'section': 'Camera',
         'key': 'iso'},
        {'type': 'numeric',
         'title': 'Shutter',
         'desc': 'Shutter speed settings of camera (=1/value)',
         'section': 'Camera',
         'key': 'shutter'},
        {'type': 'numeric',
         'title': 'Aperture',
         'desc': 'Aperture settings of camera',
         'section': 'Camera',
         'key': 'aperture'},
        {'type': 'numeric',
         'title': 'Zoom',
         'desc': 'Zoom settings of camera',
         'section': 'Camera',
         'key': 'zoom'},
    ]
)

imu_json = json.dumps(
    [
        {'type': 'title',
         'title': 'IMU Settings'},
        {'type': 'bool',
         'title': 'Calibrate',
         'desc': 'Calibrate IMU zero',
         'section': 'IMU',
         'key': 'calib'},
    ]
)

cv_json = json.dumps(
    [
        {'type': 'title',
         'title': 'Image Processing'},
        {'type': 'numeric',
         'title': 'Image Rescaling',
         'desc': 'Rate of image rescaling for transmission',
         'section': 'CV',
         'key': 'image_rescaling'},
        {'type': 'title',
         'title': 'QR decode settings'},
        {'type': 'bool',
         'title': 'ZXing library installed',
         'desc': 'Is the QR decoding library installed on this computer',
         'section': 'CV',
         'key': 'QR_lib_installed'},
        {'type': 'string',
         'title': 'Path',
         'desc': 'The path to th zxing folder on this PC',
         'section': 'CV',
         'key': 'QR_lib_path'},
    ]
)

admin_json = json.dumps(
    [
        {'type': 'title',
         'title': 'Administration'},
        {'type': 'string',
         'title': 'Logging Path',
         'desc': 'Logging base path',
         'section': 'Admin',
         'key': 'logging path'},
        #{'type': 'string',
         #'title': 'Logging Level',
         #'desc': 'Logging level',
         #'section': 'Admin',
         #'key': 'logging_level'},
    ]
)

targets_json = json.dumps(
    [
        {'type': 'title',
         'title': 'Targets'},
        {'type': 'string',
         'title': 'Export Path',
         'desc': 'Exported target file base path',
         'section': 'Targets',
         'key': 'export_path'},
        {'type': 'string',
         'title': 'Backup export Path',
         'desc': 'Backup exported target file base path',
         'section': 'Targets',
         'key': 'export_path_backup'},
        {'type': 'string',
         'title': 'Interoperability Path',
         'desc': 'Interoperability target file base path',
         'section': 'Targets',
         'key': 'interop_path'},
    ]
)

version_json = json.dumps(
    [
        {'type': 'title',
         'title': 'TAS Ground Version 1.0.3'},
    ]
)
mp_json = json.dumps(
    [
        {'type': 'title',
         'title': 'Mission planner PC network properties'},
        {'type': 'string',
         'title': 'IP',
         'desc': 'IP address or HOSTNAME of the mission planner PC',
         'section': 'MP',
         'key': 'mp_ip'},
        {'type': 'string',
         'title': 'Folder Name',
         'desc': 'The name of the network folder which contain the relevant data',
         'section': 'MP',
         'key': 'mp_folder'},
        {'type': 'title',
         'title': 'Other Properties'},
        {'type': 'string',
         'title': 'Max GPS points',
         'desc': 'Depending on computer power, enter the maximal number of gps points to be loaded at a time',
         'section': 'MP',
         'key': 'mp_gps'},
        {'type': 'string',
         'title': 'Grid cell height in feet',
         'desc': 'the distance between the grid lines in feet',
         'section': 'MP',
         'key': 'mp_grid_cell_height'},
        {'type': 'string',
         'title': 'Grid cell width in feet',
         'desc': 'the distance between the grid lines in feet',
         'section': 'MP',
         'key': 'mp_grid_cell_width'}
    ]
)
