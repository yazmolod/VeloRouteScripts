# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessingAlgorithm,
    )

class CsvExportAlgorithm(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    
    def initAlgorithm(self, config):
        pass

    def processAlgorithm(self, parameters, context, feedback):
        feedback.pushInfo('Hello world')
        return {}

    def name(self):
        return 'csv_export'

    def displayName(self):
        return self.tr(self.name())

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Group1'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return CsvExportAlgorithm()