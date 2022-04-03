# -*- coding: utf-8 -*-

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsMapLayer,
    QgsProcessing,
    QgsFeatureSink,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterDefinition,
    QgsProcessingParameterMapLayer,
    QgsProcessingParameterMultipleLayers,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterFeatureSink,
    QgsWkbTypes,
    QgsProcessingParameterNumber,
    QgsFields,
    QgsField,
    QgsCoordinateTransform,
    QgsProject,
    QgsFeature,
    )
from qgis.PyQt.QtCore import QVariant
from .framework import VeloGraph, iter_destination_features, TARGET_CRS, DISTANCE_CALCULATOR


class DistanceCalculateAlgorithm(QgsProcessingAlgorithm):
    """
    """

    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.

    PATHS_OUTPUT = 'PATHS_OUTPUT'
    SIGN_INPUT = 'SIGN_INPUT'
    ROADS_INPUT = 'ROADS_INPUT'
    POIS_INPUT = 'POIS_INPUT'
    TOLERANCE = 'TOLERANCE'

    def initAlgorithm(self, config):
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """
        self.addParameter(
            QgsProcessingParameterMapLayer(
                self.SIGN_INPUT,
                self.tr('Слой с носителями'),
                QgsProcessing.TypeVectorPoint
            )
        )        
        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                self.POIS_INPUT,
                self.tr('Слои с объектами'),
                QgsProcessing.TypeVectorPoint
            )
        )        
        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                self.ROADS_INPUT,
                self.tr('Слои с дорогами'),
                QgsProcessing.TypeVectorLine
            )
        )    
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.PATHS_OUTPUT,
                self.tr('Кратчайшие пути'),
                type=QgsProcessing.TypeVectorLine
            )
        )

        advanced_params = []
        advanced_params.append(QgsProcessingParameterNumber(self.TOLERANCE,
                                                   self.tr('Topology tolerance'),
                                                   QgsProcessingParameterNumber.Double,
                                                   0.0, False, 0, 99999999.99))
        for p in advanced_params:
            p.setFlags(p.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
            self.addParameter(p)



    def processAlgorithm(self, parameters, context, feedback):
        """
        Here is where the processing itself takes place.
        """
        sign_layer = self.parameterAsLayer(parameters, self.SIGN_INPUT, context)
        roads_layers = self.parameterAsLayerList(parameters, self.ROADS_INPUT, context)
        poi_layers = self.parameterAsLayerList(parameters, self.POIS_INPUT, context)
        tolerance = self.parameterAsDouble(parameters, self.TOLERANCE, context)
        
        
        
        
        path_sink, path_dest_id = self.parameterAsSink(parameters, self.PATHS_OUTPUT,
                context, path_fields, QgsWkbTypes.LineString, TARGET_CRS)

path_sink.addFeature(path_feature, QgsFeatureSink.FastInsert)
        
    

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'distance_calculate'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr(self.name())

    def group(self):
        """
        Returns the name of the group this algorithm belongs to. This string
        should be localised.
        """
        return self.tr(self.groupId())

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'Group1'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return DistanceCalculateAlgorithm()
