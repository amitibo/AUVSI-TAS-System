'''
Created on 2/11/2016

@author: adi
'''
from GraphNode import GraphNode as Node
from GraphEdge import GraphEdge as Edge

class Graph:
    '''
    classdocs
    '''
    def __init__(self):
        self.nodeList = []
        self.edgesList = []
        self.numOfEdges = 0
        self.numOfNodes = 0
    def getNumOfEdges(self):
        return self.numOfEdges
    def getNumOfNodes(self):
        return self.numOfNodes
    def __addNode(self, node):
        if not isinstance(node, Node):
            raise TypeError("node must be set to an Node")
        assert(node.getEdgesNum() == 0)
        #self.nodeList[self.numOfNodes] = node
        self.nodeList.append(node) 
    def __addEdge(self, edge):
        if not isinstance(edge, Edge):
            raise TypeError("edge must be set to an Edge")
        assert((edge.getNode1() < self.numOfNodes) or (edge.getNode2() < self.numOfNodes))
        self.nodeList[edge.getNode1()].addEdge(edge)
        self.nodeList[edge.getNode2()].addEdge(edge)
        self.edgesList.append(edge)
    def addNode(self, nodeObject):
        node = Node(self.getNumOfNodes(), nodeObject)
        self.__addNode(node)
        self.numOfNodes = self.numOfNodes + 1
        return node
    def addEdge(self, nodeid1, nodeid2, edgeObject = None):
        assert((nodeid1 < self.numOfNodes) or (nodeid2 < self.numOfNodes))
        newEdge = Edge(self.getNumOfEdges(), self.nodeList[nodeid1].getId(), self.nodeList[nodeid2].getId(),edgeObject)
        self.__addEdge(newEdge)
        self.numOfEdges = self.numOfEdges + 1
    