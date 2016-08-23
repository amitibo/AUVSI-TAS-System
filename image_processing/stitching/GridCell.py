'''
Created on 11/02/2016

@author: adi
'''

class GridCell:
    '''
    classdocs
    '''
    def __init__(self, GridX, GridY, cellArea = None):
        '''
        Constructor
        '''
        self.cellArea = cellArea     #the area the cell covers
        self.numOfObjectsInCell = 0  #the number of objects in this grid cell
        self.objectList = []         #the object in this cell
        self.GridX = GridX           # = row in grid
        self.GridY = GridY           # = col in grid
    def add(self, cellObject):
        self.objectList.append(cellObject)
        self.numOfObjectsInCell += 1
    def getObjectList(self):
        return self.objectList
    def getArea(self):
        return self.cellArea
    def getGridX(self):
        return self.GridX
    def getGridY(self):
        return self.GridY