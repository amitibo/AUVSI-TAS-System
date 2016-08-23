HOST_IP = '10.10.131.10'
TEAM_FOLDER = 'Technion'
TEAM_DIR = '/sric/%s' % TEAM_FOLDER
USERNAME = 'Technion'
PASSWORD = '5096175118'
DOWNLOAD_DIR = TEAM_DIR
DOWNLOAD_FILE = 'download.txt'
DOWNLOAD_PATH = DOWNLOAD_DIR + '/' + DOWNLOAD_FILE
UPLOAD_DIR = TEAM_DIR
UPLOAD_FILE = 'upload.txt'
UPLOAD_PATH = UPLOAD_DIR + '/' + UPLOAD_FILE
UPLOAD_LOCAL_PATH = 'sric_upload_message.txt'

__author__ = 'Ori'

import ftplib
import os
from time import sleep
from socket import timeout, error
import AUVSIground.global_settings as gs
#crad_file_local = 'crad_data.txt'

def persistent_connection(host):
    while True:
        try:
            print "Trying to connect..."
            client = ftplib.FTP(host=host)
            return client
        except timeout:
            print "Retrying"
        except error:
            print "Socket error, Retrying"
            sleep(1)


def start_sric():
    client = persistent_connection(HOST_IP)
    client.login(user=USERNAME, passwd=PASSWORD)

    client.cwd(DOWNLOAD_DIR)
    #credential_file = client.nlst()[0]

    download_file = DOWNLOAD_FILE
    print "Getting information file: " + download_file

    client.retrbinary("RETR " + download_file, parse_info)

def parse_info(data):
    data = str(data)

    try:
        with open(DOWNLOAD_FILE, 'wb') as f:
            f.write(data)
    except:
        print 'Error creating local output file'

    print "Message: '{}'".format(data)

    up_client = persistent_connection(HOST_IP)
    up_client.login(user=USERNAME, passwd=PASSWORD)
    up_client.cwd(UPLOAD_DIR)

    #crop_name = CROP_NAME
    #crop_path = os.path.join(gs.AUVSI_BASE_FOLDER, 'crops', crop_name + '.jpg')

    print "Storing file: {}".format(UPLOAD_FILE)
    up_client.storbinary("STOR " + UPLOAD_FILE, open(UPLOAD_LOCAL_PATH, 'rb'))
    print "Storing file completed"


if __name__ == "__main__":
    start_sric()
