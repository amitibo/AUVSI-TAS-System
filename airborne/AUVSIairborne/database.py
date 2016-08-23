import sqlite3
from twisted.python import log
from  datetime import datetime
import global_settings as gs
import os


def _cmd(cmd, params=()):
    
    log.msg('Executing sqlite3 cmd: {cmd}, {params}'.format(cmd=cmd, params=params))
    conn = sqlite3.connect(gs.DB_PATH)
    cursor = conn.cursor()
    cursor.execute(cmd, params)
    result = list(cursor)
    conn.commit()
    cursor.close()
    conn.close()

    return result


def initDB():
    
    #
    # Check if databases exists, if not create them
    #
    if not os.path.exists(gs.DB_FOLDER):
        os.makedirs(gs.DB_FOLDER)

    _cmd(
        cmd='create table if not exists {table_name} (id integer primary key, image_path text, data_path text, [timestamp] timestamp)'.format(table_name=gs.IMAGES_TABLE)
    )    
    

def storeImg(img_path, data_path):
    
    cmd = "INSERT INTO {table_name}(image_path, data_path, timestamp) values (?, ?, ?)".format(table_name=gs.IMAGES_TABLE)
    _cmd(cmd, (img_path, data_path, datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')))


def getNewImgs(timestamp):
    
    if timestamp is None:
        timestamp = datetime(year=1970, month=1, day=1)

    cmd = "SELECT * FROM {table_name} WHERE {table_name}.timestamp > '{timestamp}'".format(
        table_name=gs.IMAGES_TABLE,
        timestamp=timestamp
    )

    return _cmd(cmd)

