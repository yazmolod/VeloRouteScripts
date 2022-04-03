from qgis.core import (
    QgsVectorLayer,
    QgsGeometry,
    QgsFeature,
    QgsProject,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform
    )
        
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
    
    
class FeedbackImitator:
    def pushInfo(self, info):
        print(info)