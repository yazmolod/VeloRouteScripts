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
    NULL    
    )
from qgis.analysis import (
    QgsVectorLayerDirector,
    QgsGraphBuilder,
    QgsNetworkDistanceStrategy,
    )
from qgis.PyQt.QtCore import QVariant
from queue import PriorityQueue
from itertools import chain, product, combinations
from .utils import *
from math import hypot


class DistanceCalculateFramework:
    NAMERU_FIELD_NAME = 'NameRU'
    PIC_FIELD_NAME = 'PIC'
    NAMEEN_FIELD_NAME = 'NameEN'
    KM_FIELD_NAME = 'km'    
    SIGN_ROUTECODE_FIELD_NAME = 'routcode'
    ROAD_ROUTECODE_FIELD_NAME = 'CODE'
    
    TARGET_CRS = QgsCoordinateReferenceSystem("EPSG:4326")
    DISTANCE_CALCULATOR = QgsDistanceArea()
    DISTANCE_CALCULATOR.setEllipsoid('WGS84')
    
    def __init__(
            self, 
            sign_layer, 
            poi_layers, 
            main_roads_layer, 
            secondary_roads_layer, 
            height_map, 
            graph_tolerance, 
            feedback,
            ):
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
        self.current_direction = None
    
    def init_output_fields(self):
        self.output_fields = QgsFields()
        self.output_fields.append(QgsField('id', QVariant.Int))
        self.output_fields.append(QgsField('length_2d', QVariant.Double))
        self.output_fields.append(QgsField('length_3d', QVariant.Double))
        self.output_fields.append(QgsField('direction', QVariant.String))
    
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
            while pointer is not None:
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
        for layer, feature in self.iter_pois_by_name(name):
            return layer, feature
        else:
            return None, None
    
    def iter_pois_by_name(self, name):
        for layer in self.poi_layers:
            for feature in layer.getFeatures():
                if self.feature_has_field(feature, self.NAMERU_FIELD_NAME) and feature[self.NAMERU_FIELD_NAME] == name:
                    yield layer, feature
                                 
        
    def iter_directions(self):
        nums = range(1,5)
        dirs = ['A', 'B']
        for i in product(nums, dirs):
            direction = ''.join(map(str, i))
            self.current_direction = direction
            yield direction
                                                    
        
    def calculate_path_distance(self, vertex_ids):
        l = 0
        for i in range(len(vertex_ids)-1):
            v1 = vertex_ids[i]
            v2 = vertex_ids[i+1]
            l += self.calc_vertex_distance(v1, v2)
        return l
    
    def make_path_feature(self, vertex_ids):
        feature = QgsFeature()
        feature.setFields(self.output_fields)
        path_line = self.linestring_from_vertex(vertex_ids)
        feature.setGeometry(path_line)
        feature['length_3d'] = self.calculate_path_distance(vertex_ids)
        feature['length_2d'] = self.DISTANCE_CALCULATOR.measureLength(path_line)
        feature['direction'] = self.current_direction
        return feature
    
    def get_closest_road(self, sign_feature):
        geom = xform_geometry(sign_feature.geometry(), self.sign_layer.sourceCrs(), self.main_roads_layer.sourceCrs())        
        nearest_ids = self.main_road_spatial.nearestNeighbor(geom.asPoint(), 1)
        for nearest_id in nearest_ids:
            features = self.main_roads_layer.getFeatures(QgsFeatureRequest(nearest_id))
            for f in features:
                return f
            
    def feature_has_field(self, feature, fieldname):
        return fieldname in [i.name() for i in feature.fields()]
    
    def feature_has_fields(self, feature, *fieldnames):
        return all(self.feature_has_field(feature, i) for i in fieldnames)
            
    def is_service(self, feature, direction):
        pic_field = '{}_{}'.format(self.PIC_FIELD_NAME, direction)
        nameru_field = '{}{}'.format(self.NAMERU_FIELD_NAME, direction)
        if self.feature_has_fields(feature, pic_field, nameru_field):
            if feature[pic_field] != NULL and feature[pic_field] != 'N/A' and feature[nameru_field] == NULL:
                return True   #TODO             
        return False
        
    def get_shortest_path_feature(self, sign_feature, poi_layer, poi_feature):
        sign_geom = xform_geometry_4326(sign_feature.geometry(), self.sign_layer.sourceCrs())
        poi_geom = xform_geometry_4326(poi_feature.geometry(), poi_layer.sourceCrs())
        # calc shortest path
        vertex_ids = self.shortest_path(sign_geom.asPoint(), poi_geom.asPoint())
        if not vertex_ids:
            self.feedback.reportError('[processAlgorithm] Cannot build shortest path')
            return None
        else:
            # self.feedback.pushInfo('[processAlgorithm] Shortest path calculated')
            # make path feature
            path_feature = self.make_path_feature(vertex_ids)
            return path_feature
        
        
    def find_closest_service(self, sign_feature, service_name):
        reversed = self.current_direction[0] == 'B' 
        ok_service_layer = ok_service_feature = None
        min_distance = None
        for service_layer, service_feature in self.iter_pois_by_name(service_name):
            path = self.get_shortest_path_feature(sign_feature, service_layer, service_feature)
            path_length = path['length_3d']
            if True:    # тут должна быть проверка на направление
                if min_distance is None or path_length < min_distance:
                    min_distance = path_length
                    ok_service_layer, ok_service_feature = service_layer, service_feature
        if ok_service_feature:
            return PackedFeature(ok_service_feature, ok_service_layer)
    
    def check_distance_beetween_services(self, service_packed_features):
        for pair in combinations(service_packed_features, 2):
            pt1 = pair[0].get_4326_geometry().asPoint()
            pt2 = pair[1].get_4326_geometry().asPoint()
            distance = self.DISTANCE_CALCULATOR.measureLine(pt1, pt2)
            if distance > 100:
                return False
        return True
        
        
    def main(self):
        # Compute the number of steps to display within the progress bar and
        # get features from source
        self.feedback.setProgress(0)
        total = 100.0 / (self.sign_layer.featureCount()*8) if self.sign_layer.featureCount() else 0        
        counter = 1
        self.sign_layer.startEditing()
        for sign_feature in self.sign_layer.getFeatures():
            # если была нажата кнопка cancel - прерываемся
            if self.feedback.isCanceled():
                break
            # general feature fields
            sign_feature[self.SIGN_ROUTECODE_FIELD_NAME] = self.get_closest_road(sign_feature)[self.ROAD_ROUTECODE_FIELD_NAME]
            # iter all direction fields
            for direction in self.iter_directions():
                if self.is_service(sign_feature, direction):
                    service_paths = []
                    service_packed_features = []
                    # find shortest path for every service
                    service_names = sign_feature[self.PIC_FIELD_NAME + '_' + direction].split(' ')
                    for service_name in service_names:
                        service_packed_feature = self.find_closest_service(sign_feature, service_name)
                        if service_packed_feature:
                            path_feature = self.get_shortest_path_feature(sign_feature, service_packed_feature.layer, service_packed_feature.feature)
                            service_paths.append(path_feature)
                            service_packed_features.append(service_packed_feature)
                        else:
                            self.feedback.pushInfo(f"Can't find service {service_name}")
                            
                    # all paths find and all shortest than 100 meters
                    if service_paths:
                        if self.check_distance_beetween_services(service_packed_features):
                            closest_service_path = min(service_paths, key=lambda x: x['length_3d'])
                            sign_feature[self.KM_FIELD_NAME + '_' + direction] = self.format_length(closest_service_path['length_3d'])
                            yield closest_service_path
                        else:
                            self.feedback.pushInfo(f"Service distance more than 100 meters")
                            sign_feature[self.KM_FIELD_NAME + '_' + direction] = 'N/A'
                    else:
                        self.feedback.pushInfo(f"No services found")
                        sign_feature[self.KM_FIELD_NAME + '_' + direction] = 'N/A'
                else:
                    # direction feature fields
                    poi_layer, poi_feature = self.find_poi_by_name(sign_feature[self.NAMERU_FIELD_NAME + direction])
                    if poi_feature is None:
                        sign_feature[self.PIC_FIELD_NAME + '_' + direction] = 'N/A'
                        sign_feature[self.NAMEEN_FIELD_NAME + direction] = 'N/A'
                        sign_feature[self.KM_FIELD_NAME + '_' + direction] = 'N/A'
                    else:
                        sign_feature[self.PIC_FIELD_NAME + '_' + direction] = poi_feature[self.PIC_FIELD_NAME.lower()]
                        sign_feature[self.NAMEEN_FIELD_NAME + direction] = poi_feature[self.NAMEEN_FIELD_NAME]
                        path_feature = self.get_shortest_path_feature(sign_feature, poi_layer, poi_feature)
                        if path_feature:
                            sign_feature[self.KM_FIELD_NAME + '_' + direction] = self.format_length(path_feature['length_3d'])
                            yield path_feature
                        else:
                            sign_feature[self.KM_FIELD_NAME + '_' + direction] = 'N/A'              
                # Update the progress bar
                self.feedback.setProgress(counter / total * 100)
                counter += 1    
            self.sign_layer.updateFeature(sign_feature)
        self.sign_layer.commitChanges()


    def format_length(self, length):
        km = length / 1000
        if km >= 10:
            formatted_km = str(int(km))
        else:
            formatted_km = str(round(km, 1)).replace('.0', '')
        return formatted_km


                