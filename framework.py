# -*- coding: utf-8 -*-

from VeloRouteScripts import utils
from qgis.core import (
    QgsProject,
    QgsCoordinateTransform,
    QgsCoordinateReferenceSystem,
    QgsPointXY,
    QgsDistanceArea,
    QgsLineString,
    QgsVectorLayer,
    QgsFeature,
    QgsGeometry,
    )
from qgis.analysis import (
    QgsVectorLayerDirector,
    QgsGraphBuilder,
    QgsNetworkDistanceStrategy,
    )
from qgis.PyQt.QtCore import QVariant
from queue import PriorityQueue
from itertools import chain

TARGET_CRS = QgsCoordinateReferenceSystem("EPSG:4326")
DISTANCE_CALCULATOR = QgsDistanceArea()
DISTANCE_CALCULATOR.setEllipsoid('WGS84')

class VeloGraph:
    def __init__(self, input_roads_layers, input_points_layers, input_tolerance, feedback):
        self.feedback = feedback
        merged_road_layer = self.merge_road_layers(input_roads_layers)
        self.director = QgsVectorLayerDirector(
            merged_road_layer, 
            directionFieldId = -1, 
            directDirectionValue=None, 
            reverseDirectionValue=None, 
            bothDirectionValue=None, 
            defaultDirection=QgsVectorLayerDirector.DirectionBoth
        )
        self.director.addStrategy(QgsNetworkDistanceStrategy())
        self.builder = QgsGraphBuilder(TARGET_CRS, True, input_tolerance)
        self.additional_points = self.convert_input_point_layers(input_points_layers)
        self.tied_points_list = self.director.makeGraph(self.builder, self.additional_points, self.feedback)
        utils.log('Graph init...', 'VeloGraph', '__init__', feedback=self.feedback)
        self.network = self.builder.graph()
        utils.log('Graph builded', 'VeloGraph', '__init__', feedback=self.feedback)
        self.make_tied_edges()
        
    def merge_road_layers(self, layers):
        merged_layer = QgsVectorLayer('LineString', 'merged_edges', 'memory')
        merged_layer.setCrs(TARGET_CRS)
        features = []
        for layer in layers:
            xform = QgsCoordinateTransform(layer.sourceCrs(), TARGET_CRS, QgsProject.instance())    
            for feature in layer.getFeatures():
                geom = feature.geometry()
                geom.transform(xform)
                feature.setGeometry(geom)
                features.append(feature)
        provider = merged_layer.dataProvider()
        provider.addFeatures(features)
        return merged_layer
        
    def make_tied_edges(self):
        for add_pt, tied_pt in zip(self.additional_points, self.tied_points_list):
            add_id = self.network.addVertex(add_pt)
            tied_id = self.network.findVertex(tied_pt)
            self.network.addEdge(add_id, tied_id, [QgsNetworkDistanceStrategy()])
        
    def convert_input_point_layers(self, layers):
        '''reproject layers geometry in EPSG4326 and extract points'''
        points = []
        for layer in layers:
            xform = QgsCoordinateTransform(layer.sourceCrs(), TARGET_CRS, QgsProject.instance())
            for feature in layer.getFeatures():
                geom = feature.geometry()
                geom.transform(xform)
                points.append(geom.asPoint())
        return points
        
    def draw_edges(self):
        layer = QgsVectorLayer('LineString', 'GraphEdges', 'memory')
        features = []
        for i in range(self.network.edgeCount()):
            edge = self.network.edge(i)
            pts = [self.network.vertex(edge.fromVertex()).point(), self.network.vertex(edge.toVertex()).point()]
            feature = QgsFeature()
            feature.setGeometry(QgsGeometry.fromPolylineXY(pts))
            fields = QgsFields()
            fields.append(QgsField('edge_id', QVariant.Int))
            #fields.append(QgsField('cost', QVariant.Double))
            feature.setFields(fields)
            feature['edge_id'] = i
            #feature['cost'] = edge.cost()
            features.append(feature)
        provider = layer.dataProvider()
        provider.addFeatures(features)
        QgsProject.instance().addMapLayer(layer)
    
    def draw_vertexes(self):
        layer = QgsVectorLayer('Point', 'GraphVertexes', 'memory')
        features = []
        for i in range(self.network.vertexCount()):
            vertex = self.network.vertex(i)
            point = vertex.point()
            feature = QgsFeature()
            feature.setGeometry(QgsGeometry.fromPointXY(point))
            fields = QgsFields()
            fields.append(QgsField('vertex_id', QVariant.Int))
            feature.setFields(fields)
            feature['vertex_id'] = i
            features.append(feature)
        provider = layer.dataProvider()
        provider.addFeatures(features)
        QgsProject.instance().addMapLayer(layer)
            
    def draw_graph(self):
        '''debug purpose'''
        self.draw_vertexes()
        self.draw_edges()
       
    def calc_distance(self, from_vertex_id: int, to_vertex_id: int):
        pt1 = self.network.vertex(from_vertex_id).point()
        pt2 = self.network.vertex(from_vertex_id).point()
        m = DISTANCE_CALCULATOR.measureLine(pt1, pt2)
        return m
    
    def iter_edges(self, vertex_id):
        vertex = self.network.vertex(vertex_id)
        for iedge in vertex.incomingEdges():
            yield self.network.edge(iedge)    
        for iedge in vertex.outgoingEdges():
            yield self.network.edge(iedge)     
            
    def cost(self, edge):
        return self.calc_distance(edge.fromVertex(), edge.toVertex()) 
    
    def shortest_path(self, from_geometry: QgsPointXY, to_geometry: QgsPointXY):
        start_vertex_id = self.network.findVertex(from_geometry)
        finish_vertex_id = self.network.findVertex(to_geometry)
        if start_vertex_id == -1:
            raise Exception('Cant find start point on graph')
        if finish_vertex_id == -1:
            raise Exception('Cant find finish point on graph')
        print(start_vertex_id, finish_vertex_id)
        # init
        frontier = PriorityQueue()
        frontier.put((0, start_vertex_id))
        came_from = dict()
        cost_so_far = dict()
        came_from[start_vertex_id] = None
        cost_so_far[start_vertex_id] = 0
        # searching (A* algorithm)
        while not frontier.empty():            
            _, current_vertex_id = frontier.get()
            if current_vertex_id == finish_vertex_id:
                break
            for edge in self.iter_edges(current_vertex_id):
                next_vertex_id = edge.fromVertex() if edge.fromVertex() != current_vertex_id else edge.toVertex()
                new_cost = cost_so_far[current_vertex_id] + self.cost(edge)
                if next_vertex_id not in cost_so_far or new_cost < cost_so_far[next_vertex_id]:
                    cost_so_far[next_vertex_id] = new_cost
                    priority = new_cost + self.calc_distance(next_vertex_id, finish_vertex_id)
                    frontier.put((priority, next_vertex_id))
                    came_from[next_vertex_id] = current_vertex_id  
        # construct path
        vertex_ids_path = []
        pointer = finish_vertex_id
        if finish_vertex_id not in came_from:
            utils.log('Path not found', 'VeloGraph', 'shortest_path', feedback=self.feedback)
            return None
        else:
            while pointer:
                vertex_ids_path.append(pointer)
                pointer = came_from[pointer]
            return vertex_ids_path
    
    def path_vector(self, vertex_ids_path):
        pts = [self.network.vertex(i).point() for i in vertex_ids_path]
        line = QgsGeometry.fromPolylineXY(pts)
        return line
        
        
def iter_nameru_fields(feature):
    for field in feature.fields():
        field_name = field.name()
        if field_name.lower().startswith('nameru'):
            yield field_name, feature.attribute(field_name)
        
def find_feature_by_name(name, layers):
    for layer in layers:
        for feature in layer.getFeatures():
            for nameru_name, nameru_value in iter_nameru_fields(feature):
                if nameru_value == name:
                    return layer, feature
                
def iter_destination_paths(sign_layer, poi_layers, feedback):
    for sign_feature in sign_layer.getFeatures():
        utils.log('Process feature ' + str(sign_feature['id']), 'Framework', feedback=feedback)
        for sign_field_name,sign_field_value in iter_nameru_fields(sign_feature):
            # utils.log('Proccess attribute '+ sign_field_name, 'Framework', feedback=feedback)
            if not sign_field_value:
                utils.log('No value for attribute '+ sign_field_name, 'Framework', feedback=feedback)
            else:
                # utils.log('Searching for '+ sign_field_value, 'Framework', feedback=feedback)
                result = find_feature_by_name(sign_field_value, poi_layers)
                if result is None:
                    utils.log(sign_field_value + ' not found', 'Framework', feedback=feedback)
                else:
                    utils.log(sign_field_value + ' founded, calculating shortest path', 'Framework', feedback=feedback)
                    poi_layer, poi_feature = result
                    yield poi_layer, poi_feature, sign_feature

# sign_layer = QgsProject.instance().mapLayersByName('123_DIR')[0]
# transport = QgsProject.instance().mapLayersByName('transport')[0]
# poi = QgsProject.instance().mapLayersByName('POI')[0]
# services = QgsProject.instance().mapLayersByName('services')[0]
# locality = QgsProject.instance().mapLayersByName('locality')[0]
# poi_layers = [transport, poi, services, locality]

# first = QgsProject.instance().mapLayersByName('main_route')[0]   
# second = QgsProject.instance().mapLayersByName('secondary_routes')[0]   
# third = QgsProject.instance().mapLayersByName('test route')[0]
# roads = [first, second, third]

# graph = VeloGraph(roads, [sign_layer]+poi_layers)
# sign_feature = next(sign_layer.getFeatures())

# layer = QgsVectorLayer('LineString', 'paths', 'memory')
# fields = QgsFields()
# fields.append(QgsField('id', QVariant.Int))
# fields.append(QgsField('from', QVariant.String))
# fields.append(QgsField('to', QVariant.String))
# fields.append(QgsField('length', QVariant.Double))
# features = []
# fid = 0
# for poi_feature, path_line in iter_destination_paths(sign_feature, poi_layers):
#     feature = QgsFeature()
#     feature.setGeometry(path_line)
#     feature.setFields(fields)
#     feature['id'] = fid
#     feature['from'] = sign_feature['Name']
#     feature['to'] = poi_feature['NameRU']
#     feature['length'] = DISTANCE_CALCULATOR.measureLength(path_line)
#     features.append(feature)
#     fid += 1
# provider = layer.dataProvider()
# provider.addFeatures(features)
# provider.addAttributes(fields)
# QgsProject.instance().addMapLayer(layer)


                