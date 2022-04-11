from qgis.core import (
    QgsVectorLayer,
    QgsGeometry,
    QgsFeature,
    QgsProject,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform
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