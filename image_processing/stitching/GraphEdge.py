'''
Created on 2/11/2016

@author: adi
'''

class GraphEdge:
    '''
    classdocs
    '''

    def __init__(self, edgeId, nodeId1, nodeId2, edgeObject):
        '''
        Constructor
        '''
        if not isinstance(nodeId1, int):
            raise TypeError("nodeId1 must be set to an int")
        if not isinstance(nodeId2, int):
            raise TypeError("nodeId2 must be set to an int")
        if not isinstance(edgeId, int):
            raise TypeError("id must be set to an int")
        assert(nodeId1 != nodeId2)
        self.id = edgeId
        self.nodeId1 = nodeId1
        self.nodeId2 = nodeId2
        self.edgeObject = edgeObject
    def getNode1(self):
        return self.nodeId1
    def getNode2(self):
        return self.nodeId2
    def getEdgeId(self):
        return self.id
    def getEdgeObject(self):
        return self.edgeObject
    