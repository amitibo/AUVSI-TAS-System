'''
Created on 11/02/2016 

@author: adi
'''

class Area:
    '''
    classdocs
    '''
    def __init__(self, xMin, xMax, yMin, yMax):
        '''
        Constructor
        '''
        self.xMin = xMin
        self.xMax   = xMax
        self.yMin = yMin
        self.yMax   = yMax
    def __str__(self):
        return "x:("+str(self.xMin)+","+str(self.xMax)+"), y:("+str(self.yMin)+","+str(self.yMax)+")"
    def getXRange(self):
        return (self.xMin, self.xMax)
    def getYRange(self):
        return (self.yMin, self.yMax)
    def xMin(self):
        return self.xMin
    def xMax(self):
        return self.xMax
    def yMin(self):
        return self.yMin
    def yMax(self):
        return self.yMax