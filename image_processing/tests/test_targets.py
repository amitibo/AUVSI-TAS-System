from __future__ import division
import AUVSIcv
import numpy as np
import json
import cv2
import glob
import os
import time


IMG_INDEX = 62


def targetSet1(longitude, latitude):
    
    targets = []
    for i in range(10):
        targets.append(
            AUVSIcv.TrapezoidTarget(
                size=1,
                orientation=30*i,
                altitude=0,
                longitude=longitude+0.00002*i,
                latitude=latitude+0.00003*i, 
                color=(70, 150, 100), 
                letter='d', 
                font_color=(140, 230, 240)
            )
        )
        
    
    targets.append(
        AUVSIcv.QRTarget(
            size=1,
            orientation=20,
            altitude=0,
            longitude=longitude,
            latitude=latitude,
            text='www.google.com'
        )
    )
    
    return targets


def targetSet2(longitude, latitude):
    
    targets = []
    for i in range(40):
        targets.append(
            AUVSIcv.randomTarget(
                longitude=longitude,
                latitude=latitude,
                altitude=0
            )[0]
        )
        
    return targets

    
def main():

    base_path = os.environ['AUVSI_CV_DATA']
    imgs_paths = sorted(glob.glob(os.path.join(base_path, 'renamed_images', '*.jpg')))
    data_paths = sorted(glob.glob(os.path.join(base_path, 'flight_data', '*.json')))

    for i, targetSet in enumerate((targetSet1, targetSet2)):
        img = AUVSIcv.Image(imgs_paths[IMG_INDEX], data_paths[IMG_INDEX], K=AUVSIcv.global_settings.K)

        for target in targetSet(img._longitude, img._latitude):        
            img.paste(target)
        
        cv2.namedWindow('image%d'%i, flags=cv2.WINDOW_NORMAL)
        cv2.imshow('image%d'%i, img.img)
        
    cv2.waitKey(0)
        
    cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
    