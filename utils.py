from qgis.core import (
    QgsVectorLayer,
    QgsGeometry,
    QgsFeature,
    QgsProject,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeatureRequest,
    QgsSpatialIndex
    )
import re
        
def draw_line(crs, *geometries):
    layer = QgsVectorLayer('MultiLineString', 'debug', "memory")
    layer.setCrs(crs)
    points = [i.asPoint() for i in geometries]
    geometry = QgsGeometry.fromPolylineXY(points)
    feature = QgsFeature()
    feature.setGeometry(geometry)
    features = [feature]
    provider = layer.dataProvider()
    provider.addFeatures(features)
    QgsProject.instance().addMapLayer(layer)
    
def xform_geometry(geometry, source_crs, target_crs):
        xform = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance())
        geometry.transform(xform)
        return geometry
    
def xform_geometry_4326(geometry, source_crs):
        return xform_geometry(geometry, source_crs, QgsCoordinateReferenceSystem("EPSG:4326"))

def get_route_codes():
    layer = get_main_road_layer()
    if not layer:
        # raise Exception("Can't find main route layer")
        return []
    else:
        codes = set(f['CODE'] for f in layer.getFeatures())
        return list(codes)
            
def get_main_road_layer():
    pr = QgsProject.instance()
    for k,v in pr.mapLayers().items():
        if re.findall(r'^main_route', k, re.IGNORECASE):
            return v
        

class FeedbackImitator:
    def pushInfo(self, info):
        print('[ERROR]', info)
        
    def pushInfo(self, info):
        print('[INFO]', info)
        
    def setProgress(self, v):
        pass
        
class PackedFeature:
    def __init__(self, feature, layer):
        self.feature = feature
        self.layer = layer
        
    def get_transformed_geometry(self, target_crs):
        geometry = self.feature.geometry()
        xform = QgsCoordinateTransform(self.layer.sourceCrs(), target_crs, QgsProject.instance())
        geometry.transform(xform)
        return geometry
    
    def get_4326_geometry(self):
        return self.get_transformed_geometry(QgsCoordinateReferenceSystem("EPSG:4326"))
    
    @classmethod
    def from_layer(cls, layer):
        return [cls(i, layer) for i in layer.getFeatures()]
        
### POINTS SORTING ###

def grouping_points(road_layer, poi_packed_features):
    spatial = QgsSpatialIndex(road_layer.getFeatures())
    groups = {}
    for pt_f in poi_packed_features:
        neighbor = spatial.nearestNeighbor(pt_f.get_transformed_geometry(road_layer.sourceCrs()).asPoint(), 1)[0]
        group = groups.get(neighbor, [])
        group.append(pt_f)
        groups[neighbor] = group
    return groups

def get_centroid_coords(packed_feature):
        pt = packed_feature.feature.geometry().centroid()
        return -pt.asPoint().x(), pt.asPoint().y()

def is_road_feature_reversed(road_packed_feature):
    start_pt = road_packed_feature.feature.geometry().asMultiPolyline()[0][0]
    end_pt = road_packed_feature.feature.geometry().asMultiPolyline()[0][-1]
    diff = end_pt - start_pt
    return diff.y() < 0 and diff.x() > 0

def sort_grouped_points(road_packed_feature, poi_packed_features):
    reversed = is_road_feature_reversed(road_packed_feature)
    return sorted(
        poi_packed_features,
        key=lambda x: road_packed_feature.feature.geometry().lineLocatePoint(x.get_transformed_geometry(road_packed_feature.layer.sourceCrs())),
        reverse=reversed
        )

def iter_pois_along_road(road_layer, poi_layers, feedback):
    road_packed_feature_from_id = lambda x: PackedFeature(next(road_layer.getFeatures(QgsFeatureRequest(x))), road_layer)
    poi_packed_features = []
    for l in poi_layers:
        poi_packed_features += PackedFeature.from_layer(l)
    # grouping by closest road
    feedback.pushInfo('[IterAlongRoad] Grouping points')
    grouping_result = grouping_points(road_layer, poi_packed_features)
    # sorting roads by centoids
    feedback.pushInfo('[IterAlongRoad] Sorting roads')
    sorted_grouping_keys = sorted(
        grouping_result.keys(), 
        key=lambda x: get_centroid_coords(road_packed_feature_from_id(x)))
    # iter sorted roads
    for road_id in sorted_grouping_keys:
        feedback.pushInfo(f'[IterAlongRoad] Yield points for road {road_id}')
        pt_group = grouping_result[road_id]
        road_packed_feature = road_packed_feature_from_id(road_id)
        # sort points linked to road
        pt_group_sorted = sort_grouped_points(road_packed_feature, pt_group)
        for pt_f in pt_group_sorted:
            yield pt_f.feature
#    