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
    QgsSpatialIndex,
    QgsGeometry,
    QgsRaster,
    QgsFields,
    QgsFeatureRequest,
    QgsField,
    
    )
from qgis.analysis import (
    QgsVectorLayerDirector,
    QgsGraphBuilder,
    QgsNetworkDistanceStrategy,
    )
from qgis.PyQt.QtCore import QVariant
from queue import PriorityQueue
from itertools import chain
from .utils import *
from math import hypot



class DistanceCalculateFramework:
    TARGET_CRS = QgsCoordinateReferenceSystem("EPSG:4326")
    FIELD_NAME_TEMPLATES = {
        'NameEN{}{}':'NameEN',
        'PIC_{}{}':'pic',
        }
    
    SIGN_ROUTECODE_FIELD_NAME = 'routcode'
    ROAD_ROUTECODE_FIELD_NAME = 'CODE'
    DISTANCE_CALCULATOR = QgsDistanceArea()
    DISTANCE_CALCULATOR.setEllipsoid('WGS84')
    
    def __init__(self, sign_layer, poi_layers, main_roads_layer, secondary_roads_layer, height_map, graph_tolerance, feedback):
        self.feedback = feedback
        self.sign_layer = sign_layer
        self.poi_layers = poi_layers
        self.main_roads_layer = main_roads_layer
        self.secondary_roads_layer = secondary_roads_layer
        self.graph_tolerance = graph_tolerance
        self.height_provider = height_map.dataProvider() if height_map else None
        self.main_road_spatial = QgsSpatialIndex(self.main_roads_layer.getFeatures())
        self.init_output_fields()
        self.build_graph()
    
    def init_output_fields(self):
        self.output_fields = QgsFields()
        self.output_fields.append(QgsField('id', QVariant.Int))
        self.output_fields.append(QgsField('length_2d', QVariant.Double))
        self.output_fields.append(QgsField('length_3d', QVariant.Double))
    
    def build_graph(self):
        # collect all points and transform them
        additional_points = []
        for layer in [self.sign_layer] + self.poi_layers:
            for feature in layer.getFeatures():
                geom = xform_geometry_4326(feature.geometry(), layer.sourceCrs())
                additional_points.append(geom.asPoint())
        # build graph
        paths = self.merge_linestring_layers(self.main_roads_layer, self.secondary_roads_layer)
        director = QgsVectorLayerDirector(
            paths, 
            directionFieldId = -1, 
            directDirectionValue=None, 
            reverseDirectionValue=None, 
            bothDirectionValue=None, 
            defaultDirection=QgsVectorLayerDirector.DirectionBoth
        )
        director.addStrategy(QgsNetworkDistanceStrategy())
        builder = QgsGraphBuilder(self.TARGET_CRS, True, self.graph_tolerance)
        tied_points_list = director.makeGraph(builder, additional_points, self.feedback)
        self.feedback.pushInfo('Graph init...')
        self.network = builder.graph()
        # make tied edges
        for add_pt, tied_pt in zip(additional_points, tied_points_list):
            add_id = self.network.addVertex(add_pt)
            tied_id = self.network.findVertex(tied_pt)
            self.network.addEdge(add_id, tied_id, [QgsNetworkDistanceStrategy()])
        self.feedback.pushInfo('Graph builded')

    def calc_vertex_distance(self, from_vertex_id: int, to_vertex_id: int):
        pt1 = self.network.vertex(from_vertex_id).point()
        pt2 = self.network.vertex(to_vertex_id).point()
        l = self.DISTANCE_CALCULATOR.measureLine(pt1, pt2)
        h = abs(self.get_elevation_at_point(pt1) - self.get_elevation_at_point(pt2))
        return hypot(l,h)
    
    def iter_vertex_edges(self, vertex_id):
        vertex = self.network.vertex(vertex_id)
        for iedge in vertex.incomingEdges():
            yield self.network.edge(iedge)    
        for iedge in vertex.outgoingEdges():
            yield self.network.edge(iedge)     
            
    def edge_cost(self, edge):
        return self.calc_vertex_distance(edge.fromVertex(), edge.toVertex())
    
    def get_elevation_at_point(self, pt):
        if self.height_provider:
            res = self.height_provider.identify(pt, QgsRaster.IdentifyFormatValue)
            if res:
                return res.results()[1]
        return 0

    
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
            for edge in self.iter_vertex_edges(current_vertex_id):
                next_vertex_id = edge.fromVertex() if edge.fromVertex() != current_vertex_id else edge.toVertex()
                new_cost = cost_so_far[current_vertex_id] + self.edge_cost(edge)
                if next_vertex_id not in cost_so_far or new_cost < cost_so_far[next_vertex_id]:
                    cost_so_far[next_vertex_id] = new_cost
                    priority = new_cost + self.calc_vertex_distance(next_vertex_id, finish_vertex_id)
                    frontier.put((priority, next_vertex_id))
                    came_from[next_vertex_id] = current_vertex_id  
        # construct path
        vertex_ids_path = []
        pointer = finish_vertex_id
        if finish_vertex_id not in came_from:
            self.feedback.pushInfo('Path not found')
            return None
        else:
            while pointer:
                vertex_ids_path.append(pointer)
                pointer = came_from[pointer]
            return vertex_ids_path
    
    def linestring_from_vertex(self, vertex_ids_path):
        pts = [self.network.vertex(i).point() for i in vertex_ids_path]
        line = QgsGeometry.fromPolylineXY(pts)
        return line
    

        
    def merge_linestring_layers(self, *layers):
        merged_layer = QgsVectorLayer('LineString', 'merged_edges', 'memory')
        merged_layer.setCrs(self.TARGET_CRS)
        features = []
        for layer in layers:
            xform = QgsCoordinateTransform(layer.sourceCrs(), self.TARGET_CRS, QgsProject.instance())    
            for feature in layer.getFeatures():
                xgeom = xform_geometry_4326(feature.geometry(), layer.sourceCrs())
                feature.setGeometry(xgeom)
                features.append(feature)
        provider = merged_layer.dataProvider()
        provider.addFeatures(features)
        return merged_layer
            
        
        
    def find_poi_by_name(self, name):
        for layer in self.poi_layers:
            for feature in layer.getFeatures():
                for nameru_name, nameru_value in self.iter_nameru_fields(feature):
                    if nameru_value == name:
                        return layer, feature
                    
        
    def iter_nameru_fields(self, feature):
        for field in feature.fields():
            field_name = field.name()
            if field_name.lower().startswith('nameru'):
                yield field_name, feature.attribute(field_name)
        
    def iter_destination_features(self, sign_feature):
        self.feedback.pushInfo('Process feature ' + str(sign_feature['id']))
        for sign_field_name, sign_field_value in self.iter_nameru_fields(sign_feature):
            if not sign_field_value:
                self.feedback.pushInfo('No value for attribute '+ sign_field_name)
            else:
                result = self.find_poi_by_name(sign_field_value)
                if result is None:
                    self.feedback.pushInfo(sign_field_value + ' not found')
                    yield sign_field_name, None, None
                else:
                    self.feedback.pushInfo(sign_field_value + ' founded, calculating shortest path')
                    poi_layer, poi_feature = result
                    yield sign_field_name, poi_layer, poi_feature 
                        
                        
    def extract_sign_direction_and_position(self, field_name):
        sign_position = field_name[-2]
        sign_direction = field_name[-1]
        return sign_position, sign_direction
        
    def calculate_path_distance(self, vertex_ids):
        l = 0
        for i in range(len(vertex_ids)-1):
            v1 = vertex_ids[i]
            v2 = vertex_ids[i+1]
            l += self.calc_vertex_distance(v1, v2)
        return l
    
    def make_path_feature(self, fid, vertex_ids):
        feature = QgsFeature()
        feature.setFields(self.output_fields)
        path_line = self.linestring_from_vertex(vertex_ids)
        feature.setGeometry(path_line)
        feature['id'] = fid
        feature['length_3d'] = self.calculate_path_distance(vertex_ids)
        feature['length_2d'] = self.DISTANCE_CALCULATOR.measureLength(path_line)
        return feature
    
    def get_closest_road(self, sign_feature):
        geom = xform_geometry(sign_feature.geometry(), self.sign_layer.sourceCrs(), self.main_roads_layer.sourceCrs())        
        nearest_ids = self.main_road_spatial.nearestNeighbor(geom.asPoint(), 1)
        for nearest_id in nearest_ids:
            features = self.main_roads_layer.getFeatures(QgsFeatureRequest(nearest_id))
            for f in features:
                return f
        
        
    def main(self):
        # Compute the number of steps to display within the progress bar and
        # get features from source
        self.feedback.setProgress(0)
        total = 100.0 / (self.sign_layer.featureCount()*4) if self.sign_layer.featureCount() else 0
        
        fid = 0
        self.sign_layer.startEditing()
        for sign_feature in self.sign_layer.getFeatures():
            sign_feature[self.SIGN_ROUTECODE_FIELD_NAME] = self.get_closest_road(sign_feature)[self.ROAD_ROUTECODE_FIELD_NAME]
            for sign_field_name, poi_layer, poi_feature, in self.iter_destination_features(sign_feature):
                # если была нажата кнопка cancel - прерываемся
                if self.feedback.isCanceled():
                    break
                # копируе
                sign_position, sign_direction = self.extract_sign_direction_and_position(sign_field_name)
                for sign_field_template, poi_field_name in self.FIELD_NAME_TEMPLATES.items():
                    sign_field_name = sign_field_template.format(sign_position, sign_direction)    
                    if poi_feature is None:
                        sign_feature[sign_field_name] = 'N/A'
                    else:
                        sign_feature[sign_field_name] = poi_feature[poi_field_name]
                        
                if poi_feature:   
                    # fill distance field
                    # project points to epsg 4326
                    sign_km_field = 'km_{}{}'.format(sign_position, sign_direction)
                    sign_geom = xform_geometry_4326(sign_feature.geometry(), self.sign_layer.sourceCrs())
                    poi_geom = xform_geometry_4326(poi_feature.geometry(), poi_layer.sourceCrs())
                    # calc shortest path
                    vertex_ids = self.shortest_path(sign_geom.asPoint(), poi_geom.asPoint())
                    if not vertex_ids:
                        self.feedback.pushInfo('[processAlgorithm] Cannot build shortest path')
                        sign_feature[sign_km_field] = 'N/A'
                    else:
                        self.feedback.pushInfo('[processAlgorithm] Shortest path calculated')
                        # make path feature
                        path_feature = self.make_path_feature(fid, vertex_ids)
                        path_length_formatted = self.format_length(path_feature['length_3d'])
                        self.feedback.pushInfo(str(sign_km_field))
                        sign_feature[sign_km_field] = path_length_formatted
                        yield path_feature
                # Update the progress bar
                self.feedback.setProgress(int(fid * total))
                fid += 1    
            self.sign_layer.updateFeature(sign_feature)
        self.sign_layer.commitChanges()


    def format_length(self, length):
        km = length / 1000
        if km >= 10:
            formatted_km = str(int(km))
        else:
            formatted_km = str(round(km, 1)).replace('.0', '')
        return formatted_km

# sign_layer = QgsProject.instance().mapLayersByName('123_DIR')[0]
# transport = QgsProject.instance().mapLayersByName('transport')[0]
# poi = QgsProject.instance().mapLayersByName('POI')[0]
# services = QgsProject.instance().mapLayersByName('services')[0]
# locality = QgsProject.instance().mapLayersByName('locality')[0]
# poi_layers = [transport, poi, services, locality]
#
# height_layer = QgsProject.instance().mapLayersByName('heights')[0]
#
# main_road_layer = QgsProject.instance().mapLayersByName('main_route')[0]   
# secondary_road_layer = QgsProject.instance().mapLayersByName('secondary_routes')[0]   
# tolerance = 0
#
#
# framework = DistanceCalculateFramework(
#             sign_layer, 
#             poi_layers, 
#             main_road_layer, 
#             secondary_road_layer, 
#             height_layer, 
#             tolerance,
#             FeedbackImitator()
#             )


                