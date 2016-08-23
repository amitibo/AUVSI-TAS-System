'''
Created on 12/02/16

@author: adi
'''
import matplotlib.pyplot as plt
import cv2
import ShowGrid
import numpy as np
class ShowPic:
    '''
    classdocs
    '''

    #"iDE" or "notebook" = runningEnviroment
    def __init__(self):
        '''
        Constructor
        '''
    def draw_matches(self, img1, kp1, img2, kp2, matches, color=None): 
        """Draws lines between matching keypoints of two images.  
        """
        new_img = img1.copy()
        
        r = 15
        thickness = 2
        if color:
            c = color
            
        for m in matches:
            # Generate random color for RGB/BGR and grayscale images as needed.
            if not color: 
                c = np.random.randint(0,256,3) if len(img1.shape) == 3 else np.random.randint(0,256)
                
            # So the keypoint locs are stored as a tuple of floats.  cv2.line(), like most other things,
            # wants locs as a tuple of ints.
            #print m, dir(m)
            end1 = tuple(np.round(kp1[m.queryIdx].pt).astype(int))
            end2 = tuple(np.round(kp2[m.trainIdx].pt).astype(int))
            cv2.line(new_img, end1, end2, c, thickness)
            cv2.circle(new_img, end1, r, c, thickness)
            cv2.circle(new_img, end2, r, c, thickness)
            plt.figure(figsize=(20,10))
            plt.imshow(new_img, cmap='gray')
            plt.show()
    def showPics(self, pic, picName, pic2 = None, pic2Name = None):
        if (GUI.runningEnviroment == "notebook"):
            plt.figure(figsize=(20, 20))
            plt.subplot(221)
            plt.imshow(pic, cmap='gray')
            if (pic2 is not None):
                plt.subplot(222)
                plt.imshow(pic2, cmap='gray')            
            plt.tight_layout()
        else:
            cv2.namedWindow( picName, cv2.WINDOW_KEEPRATIO)
            cv2.imshow( picName, pic)
            if (pic2 is not None):
                cv2.namedWindow( pic2Name, cv2.WINDOW_KEEPRATIO)
                cv2.imshow( pic2Name, pic2 )
            cv2.waitKey(0)
            cv2.destroyAllWindows()     