'''
Created on 11/02/2016

@author: adi
'''
from Area import Area
from  GridCell import GridCell as Cell
import numpy as np

#from AUVSIcv.utils import memoized


#TODO :  to be able to start search area below : 0 - in searching area, maybe to add in gridCell indicatoin if in searcharea

class Grid:
    '''
    classdocs
    '''
    def __init__(self, numOfRows, numOfCols, cellSizeRow, cellSizeCol, rowFirstIndex = 0, colFirstIndex =0):
        '''
        Constructor
        '''
        self.cellSize = (cellSizeRow, cellSizeCol)

        self.gridSize = (numOfRows, numOfCols)
        self.xCellRange = (colFirstIndex, numOfCols - colFirstIndex)
        self.yCellRange = (rowFirstIndex, numOfRows - rowFirstIndex)
        
        #create matrix - Grid :  with numOfRows*numOfCols cells
        self.grid = [[Cell for x in range(numOfCols)] for y in range(numOfRows)]
        for i in range (numOfCols):
            for j in range (numOfRows):
                xMin = i * (cellSizeCol)
                xMax = (i + 1) * (cellSizeCol)
                yMin = j * (cellSizeRow)
                yMax = (j + 1) * (cellSizeRow)
                area = Area(i * (cellSizeCol), (i + 1) * (cellSizeCol), j * (cellSizeRow), (j + 1) * (cellSizeRow))
                self.grid[j][i] = Cell(j, i, area)
    def getNumOfRows(self):
        return self.gridSize[0]
    def getNumOfCols(self):
        return self.gridSize[1]

    def getCellRowsize(self):
        return self.cellSize[0]
    def getCellColsize(self):
        return self.cellSize[1]

    def isCellInGrid(self, rowIndex, colIndex):
        if ((rowIndex >= self.xCellRange[0]) and (rowIndex <= self.xCellRange[1])):
            if ((colIndex >= self.yCellRange[0]) and (colIndex <= self.yCellRange[1])):
                return True
        return False

    def getCellsAccordingToArea(self, area):
        if not isinstance(area, Area):
            raise TypeError("area must be set to an Area")

        #calc the cells that in this area
        xMin = int((area.xMin) / (self.getCellColsize()))
        xMax = int((area.xMax) / (self.getCellColsize()))
        yMin = int((area.yMin) / (self.getCellRowsize()))
        yMax = int((area.yMax) / (self.getCellRowsize()))

        assert((xMin <= xMax) and (yMin <= yMax))
        print "getCellsAccordingToArea x(" + str(xMin) + "," + str(xMax) + ") y(" +str(yMin) + "," + str(yMax) +")"

        #create a cell list lo return
        cellList = []
        colFrom = max(xMin, self.xCellRange[0])
        colTo   = min(xMax+1, self.xCellRange[1])
        rowFrom = max(yMin, self.yCellRange[0])
        rowTo = min(yMax + 1, self.yCellRange[1])

        print "colFrom:" + str(colFrom)
        print "colTo:" + str(colTo)
        print "rowFrom:" + str(rowFrom)
        print "rowTo:" + str(rowTo)

        countCells = 0
        for row in range(rowFrom, rowTo, 1):
            for col in range(colFrom, colTo, 1):
                cellList.append(self.grid[row][col])
                countCells += 1
        print "size cellListNum: "+ str(countCells)
        return cellList
        
    def getObjectsInCell(self, row, col):
        if (self.isCellInGrid(row, col)):
            return self.grid[row][col].getObjectList()
        return None

    def getObjectsInCellText(self, row,col):
        if (self.isCellInGrid(row, col)):
            objectsList = self.grid[row][col].getObjectList()
            if (len(objectsList) == 0):
                return "empty"
            else:
                objects = ""
                for o in objectsList:
                    objects = objects + str(o)
                return objects
        else:
            return "cell does not exist"

    def add(self, addObject, row,col):
        self.grid[row][col].add(addObject)
