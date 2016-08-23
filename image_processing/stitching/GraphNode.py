'''
Created on 2/11/2016

@author: adi
'''
import GraphEdge as Edge

class GraphNode:
    '''
    classdocs
    '''

    def __init__(self, nodeId, nodeObject):
        '''
        Constructor
        '''
        if not isinstance(nodeId, int):
            raise TypeError("id must be set to an int ")
        self.id = nodeId
        self.nodeObject = nodeObject
        self.edgesList = []
        self.edgesNum = 0
    def __str__(self):
        return " Node:" + str(self.id)
    def getId(self):
        return self.id
    def getNodeObject(self):
        return self.nodeObject
    def getEdgesNum(self):
        return self.edgesNum
    def setNodeObject(self, nodeObject):
        self.nodeObject = nodeObject
    def addEdge(self, edge):
        if not isinstance(edge, Edge):
            raise TypeError("edge must be set to an Edge")
        assert((edge.getNode1() == self.id) or (edge.getNode2() == self.id))
        self.edgesList.append(edge)
        self.edgesNum = self.edgesNum + 1
    def getListOfConnectedNodes(self):
        connectedNodesList = []
        for edge in self.edgesList:
            if (edge.getNode1().getId() != self.id):
                connectedNodesList.append(edge.getNode1())
            else:
                connectedNodesList.append(edge.getNode1())
        return connectedNodesList