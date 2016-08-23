import json
import glob
import os


def main():
    base_path = os.environ['AUVSI_CV_DATA']
    
    imgs_paths = glob.glob(os.path.join(base_path, '*.jpg'))
    
    for img_path in imgs_paths:
        data_path = os.path.splitext(img_path)[0]+'.txt'
        data = {
            'altitude': 100,
            'longitude': 32.8167,
            'latitude': 34.9833,
            'yaw': 0,
            'pitch': 0,
            'roll': 0
        }
    
        with open(data_path, mode='w') as f:
            json.dump(data, f)
            
            
if __name__ == '__main__':
    main()