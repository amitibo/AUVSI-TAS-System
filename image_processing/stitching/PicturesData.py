'''
Created on 11/02/16

@author: adi
'''
from Area import Area
from Graph import Graph
from Grid import Grid
from ShowGrid import ShowGrid
#from picture.Picture import Picture
#from picture import PicturePair
from sets import Set
import cv2
import numpy as np
from AUVSIcv.images import Image
from GraphNode import GraphNode
class PicturesData:
    '''
    classdocs
    '''

    def __init__(self, rowNum, colNum, cellSizeRow, cellSizeCol, isStitchingON):
        '''
        Constructor
        '''
        self.isStitchingON = isStitchingON
        if isStitchingON is False:
            return None

        self.grid = Grid(rowNum, colNum, cellSizeRow, cellSizeCol, 0, 0)
        self.graph = Graph()

        #Initialize SURF feature Detector
        self.featureDetector = cv2.SURF(extended=0, upright=0, hessianThreshold=400, nOctaves=2)

        #Initialize FLANN feature matcher
        FLANN_INDEX_KDTREE = 0
        self.index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
        self.search_params = dict(checks=50)  # or pass empty dictionary
        self.flann = cv2.FlannBasedMatcher(self.index_params, self.search_params)

    def showGrid(self):
        show = ShowGrid(self.grid)
        show.show()

    def __matchFilter(self, matches):
        # store all the good matches as per Lowe's ratio test.
        goodMatches = []
        for m, n in matches:
            if m.distance < 0.5 * n.distance:
                goodMatches.append(m)

        if len(goodMatches) < 4:
            print 'Not enough matches for homography calculation.'
            return None
        return goodMatches

    def __calcAffineTransform(self, keyPointsNewpic, destinationNewpic, keyPoints, Destination):
        matches = self.flann.knnMatch(destinationNewpic.astype(np.float32), Destination.astype(np.float32), k=2)
        matchesAfterFiltering = self.__matchFilter(matches)
        if matchesAfterFiltering is not None:
            src_pts = np.float32([keyPointsNewpic[m.queryIdx].pt for m in matchesAfterFiltering]).reshape(-1, 1, 2)[0:3, 0:2]
            dst_pts = np.float32([keyPoints[m.trainIdx].pt for m in matchesAfterFiltering]).reshape(-1, 1, 2)[0:3, 0:2]
            warp_mat = cv2.getAffineTransform(src_pts, dst_pts)
            return warp_mat

    def __calcHomographyTransform_with_RT(self, keyPointsNewpic, destinationNewpic, keyPoints, Destination):
        matches = self.flann.knnMatch(destinationNewpic.astype(np.float32), Destination.astype(np.float32), k=2)
        matchesAfterFiltering = self.__matchFilter(matches)
        if matchesAfterFiltering is not None:

            # calc Homography
            src_pts = np.float32([keyPointsNewpic[m.queryIdx].pt for m in matchesAfterFiltering]).reshape(-1, 1, 2)#[0:3,0:2]
            dst_pts = np.float32([keyPoints[m.trainIdx].pt for m in matchesAfterFiltering]).reshape(-1, 1, 2)#[0:3, 0:2]
            warp_mat, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)

            # calc R & T
            temp = mask.ravel().tolist()

            #matches_filtered = [g for g, t in zip(matchesAfterFiltering, temp) if t]
            src_pts = [np.squeeze(g) for g, t in zip(src_pts, temp) if t]
            dst_pts = [np.squeeze(g) for g, t in zip(dst_pts, temp) if t]
            I = np.array([[1., 0, 0], [0, 1, 0], [0, 0, 1]])
            R, T = self.__calculateRT(src_pts, dst_pts, I, I)
            return warp_mat , R, T

    def addPicture(self, newImage, area):
        if self.isStitchingON is False:
            return None
        # check inputs
        if not isinstance(area, Area):
            raise TypeError("area must be set to an Area")
        if not isinstance(newImage, Image):
            raise TypeError("picture must be set to an Image")

        # add image to graph and grid
        newImage.stitching_detectFeatures(self.featureDetector)
        node = self.graph.addNode(newImage)
        cells = self.grid.getCellsAccordingToArea(area)

        # get pictures in area
        setOfNodes = Set()
        for cell in cells:
            nodesInCell = cell.getObjectList()
            setOfNodes.update(nodesInCell)

        # go over pictures in area
        newImageKeyPoints, newImageDestination = newImage._stitching_keypoints, newImage._stitching_destination
        newImageOffset, newImageRotation = newImage._ProjectionOffset, newImage._ProjectionRotation
        newProjections = None
        for currNode in setOfNodes:
            print str(node) + " <-vs-> " + str(currNode)
            currKeyPoints, currDestination = currNode.getNodeObject().stitching_getImageFeatures()
            wrapMatHomograpy, R, T = self.__calcHomographyTransform_with_RT(currKeyPoints, currDestination, newImageKeyPoints, newImageDestination)

            currNodeOffset, currNodeRotation = currNode.getNodeObject()._ProjectionOffset, currNode.getNodeObject()._ProjectionRotation
            K_inv = ((1., 0, 0), (0, 1, 0), (0, 0, 1.))

            T[0] = T[0] / 10.8
            T[1] = T[1] / 24.4
            newProjections_offset = T + currNodeOffset.T  #TODO : change T according to the scale of the picture

            h = newImageOffset[2]

            #tn picture      :  scale (149L, 100L, 3L)   : (x,y,rgb)
            #resized picture :  scale (1080L, 1616L, 3L)

            newProjections_rotation = K_inv # TODO - to put R
            lookDownMatrix = np.array(((1., 0, 0), (0, 1, 0), (0, 0, -1.)))
            #newProjections = newProjections_offset.T + h * np.dot(lookDownMatrix,
            #                                                        np.dot(newProjections_rotation,
            #                                                               np.dot(K_inv, newImage._limits)))
            #newProjections = newProjections_offset.T + currNode.getNodeObject()._projections
            #destination_points = np.dot(np.linalg.inv(wrapMatHomograpy), currNode.getNodeObject()._projections)
            #destination_points = np.dot(wrapMatHomograpy, currNode.getNodeObject()._projections)
            newProjections = destination_points
            import ipdb;
            ipdb.set_trace()
            return newProjections
        for cell in cells:
            self.grid.add(node, cell.getGridX(), cell.getGridY())


    def addPictureTmpAffine(self, newImage, area):

        #check inputs
        if not isinstance(area, Area):
            raise TypeError("area must be set to an Area")
        if not isinstance(newImage, Image):
            raise TypeError("picture must be set to an Image")

        #add image to graph and grid
        newImage.stitching_detectFeatures(self.featureDetector)
        node = self.graph.addNode(newImage)
        cells = self.grid.getCellsAccordingToArea(area)

        #get pictures in area
        setOfNodes = Set()
        for cell in cells:
            nodesInCell = cell.getObjectList()
            setOfNodes.update(nodesInCell)

        #go over pictures in area
        newImageKeyPoints, newImageDestination = newImage._stitching_keypoints, newImage._stitching_destination
        newProjections = None
        for currNode in setOfNodes:
            print str(node) + " <-vs-> " + str(currNode)
            import ipdb;ipdb.set_trace()

            currKeyPoints, currDestination = currNode.getNodeObject().stitching_getImageFeatures()
            wrapMatAffine = self.__calcAffineTransform(currKeyPoints,currDestination,newImageKeyPoints, newImageDestination)

            newImageOffset, newImageRotation = newImage._ProjectionOffset, newImage._ProjectionRotation
            currNodeOffset, currNodeRotation = currNode.getNodeObject()._ProjectionOffset, currNode.getNodeObject()._ProjectionRotation
            K_inv = ((1., 0, 0), (0, 1, 0), (0, 0, 1.))

            height = node.getNodeObject()._h
            finalOffset = newImageOffset
            finalOffset[2] = height # h
            newR = np.dot(wrapMatAffine, currNode.getNodeObject()._projections)
            #newR = (height / 100) * np.dot(wrapMatAffine, np.dot(K_inv, newImage._limits))
            newProjections = newR#finalOffset[0:2] + newR
            return newProjections
        for cell in cells:
            self.grid.add(node, cell.getGridX(), cell.getGridY())

    def addPictureTmpHomography(self, picture, area):
        if not isinstance(area, Area):
            raise TypeError("area must be set to an Area")
        if not isinstance(picture, Image):
            raise TypeError("picture must be set to an Image")
        picture.stitching_detectFeatures(self.featureDetector)
        node  = self.graph.addNode(picture)
        cells = self.grid.getCellsAccordingToArea(area)
        setOfNodes = Set()
        for cell in cells:
            nodesInCell = cell.getObjectList()
            setOfNodes.update(nodesInCell)
        print "----------------------------------------------------"
        newProjections = None
        for currNode in setOfNodes:
            print str(node) + " <-vs-> " + str(currNode)
            keypoints, destination = currNode.getNodeObject().stitching_getImageFeatures()

            import ipdb;ipdb.set_trace()
            R, T = self.__calcRTBetweenPictures(keypoints, destination, picture._stitching_keypoints,picture._stitching_destination)
            #wrapMatAffine = self.__calcAffineTransform(keypoints, destination, picture._stitching_keypoints,picture._stitching_destination)
            currOffset, currRotation = picture._ProjectionOffset, picture._ProjectionRotation
            nodeOffset, nodeRotation = node.getNodeObject()._ProjectionOffset, node.getNodeObject()._ProjectionRotation
            K_inv = ((1., 0, 0), (0, 1, 0), (0, 0, 1.))

            height = node.getNodeObject()._h

            finalOffset = nodeOffset
            finalOffset[2] = height #h
            #finalOffset[0] = finalOffset[0] #+ T[1]#y --> need to calc ratio
            #finalOffset[1] = finalOffset[1] #+ T[0]#x --> need to calc ratio

            #finalRotation = np.dot(R,currRotation)
            #finalRotation = np.dot(wrapMatAffine, currRotation)

            #currOffset[0] = currOffset[0] + T[0]
            #currOffset[1] = currOffset[1] + T[1]
            #R3_4 = np.array([[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]])
            #R3_4[:,:-1] = R
            #newR = h * np.dot(np.array(((1., 0, 0), (0, 1, 0), (0, 0, -1.))), np.dot(R3_4[:3, :3], np.dot(K_inv, picture._limits)))

            #newR = height * np.dot(wrapMatAffine, np.dot(K_inv, picture._limits))
            newR = (height/100)* np.dot(wrapMatAffine, np.dot(K_inv, picture._limits))
            newProjections = finalOffset[0:2] + newR
            print "finalOffset:" + str(finalOffset)
            #print "newProjections:" + str(newProjections)
            return newProjections
            #todo :  to finish
            #pair  -  to change 
            #pair = PicturePair(node.getNodeObject(), currNode.getNodeObject())
            #if (pair.isConnected()):
            #    self.graph.addEdge(node.getId(), currNode.getId(), pair)
            #    print str(node) + "," +str(currNode) +" :connected"
            #else:
            #    print str(node) + "," +str(currNode) +" :not connected"

        for cell in cells:
            self.grid.add(node, cell.getGridX(), cell.getGridY())

    def __in_front_of_both_cameras(self, first_points, second_points, rot, trans):
        # check if the point correspondences are in front of both images

        Rt1 = np.array(((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0)))
        Rt2 = np.hstack((rot, trans.reshape(-1, 1)))

        pts = cv2.triangulatePoints(Rt1, Rt2, np.array(first_points).T[:2, ...], np.array(second_points).T[:2, ...])

        for p in pts.T:
            first_3d_point = np.dot(Rt1, p.reshape(-1, 1))
            second_3d_point = np.dot(Rt2, p.reshape(-1, 1))

            if first_3d_point[2] < 0 or second_3d_point[2] < 0:
                return False

        return True

    def __calculateRT(self, sourcePoints, destinationPoints, K, K_inv):
        F, mask = cv2.findFundamentalMat(np.array(sourcePoints), np.array(destinationPoints), cv2.FM_RANSAC, 0.1, 0.99)

        # decompose into the essential matrix
        E = K.T.dot(F).dot(K)

        # decompose essential matrix into R, t (See Hartley and Zisserman 9.13)
        U, S, Vt = np.linalg.svd(E)
        W = np.array([0.0, -1.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0]).reshape(3, 3)

        # iterate over all point correspondences used in the estimation of the fundamental matrix
        first_inliers = [K_inv.dot([p[0], p[1], 1.0]) for p in sourcePoints]
        second_inliers = [K_inv.dot([p[0], p[1], 1.0]) for p in destinationPoints]

        # Determine the correct choice of second camera matrix
        # only in one of the four configurations will all the points be in front of both cameras
        # First choice: R = U * Wt * Vt, T = +u_3 (See Hartley Zisserman 9.19)
        R = U.dot(W).dot(Vt)
        T = U[:, 2]
        if not self.__in_front_of_both_cameras(first_inliers, second_inliers, R, T):

            # Second choice: R = U * W * Vt, T = -u_3
            T = - U[:, 2]
            if not self.__in_front_of_both_cameras(first_inliers, second_inliers, R, T):

                # Third choice: R = U * Wt * Vt, T = u_3
                R = U.dot(W.T).dot(Vt)
                T = U[:, 2]

                if not self.__in_front_of_both_cameras(first_inliers, second_inliers, R, T):
                    # Fourth choice: R = U * Wt * Vt, T = -u_3
                    T = - U[:, 2]
        return (R / R[2, 2]), (T / T[2])

    def __calcRTBetweenPictures(self, keyPoints, destination, keyPoints2, Destination2):
        matches = self.flann.knnMatch(Destination2.astype(np.float32),
                                      destination.astype(np.float32),
                                      k=2)
        matchesAfterFiltering = self.__matchFilter(matches)
        if matchesAfterFiltering is not None:
            # findHomography
            src_pts = np.float32([keyPoints2[m.queryIdx].pt for m in matchesAfterFiltering]).reshape(-1, 1, 2)
            dst_pts = np.float32([keyPoints[m.trainIdx].pt for m in matchesAfterFiltering]).reshape(-1, 1, 2)

            matches = self.flann.knnMatch(destinationNewpic.astype(np.float32), Destination.astype(np.float32), k=2)
            matchesAfterFiltering = self.__matchFilter(matches)

            Matrix, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
            temp = mask.ravel().tolist()

            matches_filtered = [g for g, t in zip(matchesAfterFiltering, temp) if t]
            src_pts = [np.squeeze(g) for g, t in zip(src_pts, temp) if t]
            dst_pts = [np.squeeze(g) for g, t in zip(dst_pts, temp) if t]

            I = np.array([[1., 0, 0], [0, 1, 0], [0, 0, 1]])
            R, T = self.__calculateRT(src_pts, dst_pts, I, I)
            return R, T
        
        