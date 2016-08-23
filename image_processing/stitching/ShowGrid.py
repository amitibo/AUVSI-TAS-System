'''
Created 12/02/16

@author: adi
'''
import Tkinter

from Grid import Grid


class ShowGrid(object):
    '''
    classdocs
    '''
    

    def __init__(self, grid):
        '''
        Constructor
        '''
        if not isinstance(grid, Grid):
            raise TypeError("grid must be set to an Grid ")
        self.grid = grid
    
    def show(self):
        root = Tkinter.Tk("Grid")
        
        for r in range(self.grid.getNumOfRows()):
            for c in range(self.grid.getNumOfCols()):
                Tkinter.Label(root, text=self.grid.getObjectsInCellText(r,c),
                    borderwidth=5 ).grid(row=r,column=c)
        
        root.mainloop(  )
    
    