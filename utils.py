from qgis.core import (
    QgsVectorLayer,
    QgsGeometry,
    QgsFeature,
    QgsProject,
    )

def log(msg, *caller_info, feedback=None):
    caller_part = ''.join(['[%s]' %i for i in caller_info])
    full_msg = caller_part + ' ' + msg
    if feedback:
        feedback.pushInfo(full_msg)
    else:
        print(full_msg)
        
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