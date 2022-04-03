# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import QCoreApplication
import re
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterEnum,
    QgsProject,
    
    )

class PagesGeneratorAlgorithm(QgsProcessingAlgorithm):
    ROUTE_CODES = 'ROUTE_CODES'
    
    # custom methods
    def getRouteCodes(self):
        layer = self.getMainRouteLayer()
        if not layer:
            raise Exception("Can't find main route layer")
        codes = set(f['CODE'] for f in layer.getFeatures())
        return codes
                
    def getMainRouteLayer(self):
        pr = QgsProject.instance()
        for k,v in pr.mapLayers().items():
            if re.findall(r'^main_route', k, re.IGNORECASE):
                return v
    
    # inherited methods
    
    def initAlgorithm(self, config):
        self.addParameter(
            QgsProcessingParameterEnum(
                self.ROUTE_CODES,
                'Коды маршрутов',
                options=['test'],
                allowMultiple=True,
                )
            )

    def processAlgorithm(self, parameters, context, feedback):
        feedback.pushInfo('Hello world')
        return {}

    def name(self):
        return 'pages_generator'

    def displayName(self):
        return self.tr(self.name())

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Group1'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return PagesGeneratorAlgorithm()