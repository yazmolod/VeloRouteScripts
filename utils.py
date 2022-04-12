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
        print(info)
        
### POINTS SORTING ###

def grouping_points(road_features, point_features):
    spatial = QgsSpatialIndex(road_features)
    groups = {}
    for pt_f in point_features:
        neighbor = spatial.nearestNeighbor(pt_f.geometry().asPoint(), 1)[0]
        group = groups.get(neighbor, [])
        group.append(pt_f)
        groups[neighbor] = group
    return groups

def get_centroid_coords(feature):
        pt = feature.geometry().centroid()
        return -pt.asPoint().x(), pt.asPoint().y()

def sort_road_segments(road_features):
    return sorted(road_features, key=get_centroid_coords)

def is_road_feature_reversed(road_feature):
    start_pt = road_feature.geometry().asMultiPolyline()[0][0]
    end_pt = road_feature.geometry().asMultiPolyline()[0][-1]
    diff = end_pt - start_pt
    return diff.y() < 0 and diff.x() > 0

def sort_grouped_points(road_feature, point_features):
    reversed = is_road_feature_reversed(road_feature)
    return sorted(
        point_features,
        key=lambda x: road_feature.geometry().lineLocatePoint(x.geometry()),
        reverse=reversed
        )

def iter_pois_along_road(road_layer, poi_layers, feedback):
    road_feature_from_id = lambda x: next(road_layer.getFeatures(QgsFeatureRequest(x)))
    # приводим все объекты к одному crs
    feedback.pushInfo('[IterAlongRoad] Converting layers crs')
    poi_features = []
    for layer in poi_layers:
        for feature in layer.getFeatures():
            geom = xform_geometry(feature.geometry(), layer.sourceCrs(), road_layer.sourceCrs())
            feature.setGeometry(geom)
            poi_features.append(feature)
    # группируем точки по ближайшему участку дороги
    feedback.pushInfo('[IterAlongRoad] Grouping points')
    grouping_result = grouping_points(road_layer.getFeatures(), poi_features)
    # сортируем ключи участков дороги по удаленности центроидов
    feedback.pushInfo('[IterAlongRoad] Sorting roads')
    sorted_grouping_keys = sorted(
        grouping_result.keys(), 
        key=lambda x: get_centroid_coords(road_feature_from_id(x)))
    # итерируем отсортированные участки дорог
    for road_id in sorted_grouping_keys:
        feedback.pushInfo(f'[IterAlongRoad] Yield points for road {road_id}')
        pt_group = grouping_result[road_id]
        road_feature = road_feature_from_id(road_id)
        # также не забываем отсортировать точки по участку
        pt_group_sorted = sort_grouped_points(road_feature, pt_group)
        for pt_f in pt_group_sorted:
            yield pt_f
#    