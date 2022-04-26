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
    QgsProcessingParameterRasterLayer,
    QgsWkbTypes,
    QgsProcessingParameterNumber,
    QgsFields,
    QgsField,
    QgsCoordinateTransform,
    QgsProject,
    QgsFeature,
    QgsProcessingParameterVectorLayer,
    )
from qgis.PyQt.QtCore import QVariant
from .distance_framework import DistanceCalculateFramework


class DistanceCalculateAlgorithm(QgsProcessingAlgorithm):
    """
    """

    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.

    PATHS_OUTPUT = 'PATHS_OUTPUT'
    SIGN_INPUT = 'SIGN_INPUT'
    MAIN_ROAD_INPUT = 'MAIN_ROAD_INPUT'
    SECONDARY_ROAD_INPUT = 'SECONDARY_ROAD_INPUT'
    POIS_INPUT = 'POIS_INPUT'
    HEIGHTS_INPUT = 'HEIGHTS_INPUT'
    TOLERANCE = 'TOLERANCE'

    def initAlgorithm(self, config):
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.SIGN_INPUT,
                self.tr('Слой с носителями'),
                types=[QgsProcessing.TypeVectorPoint],
                defaultValue='123_DIR'
            )
        )        
        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                self.POIS_INPUT,
                self.tr('Слои с объектами'),
                QgsProcessing.TypeVectorPoint,
                defaultValue=['POI', 'locality', 'transport', 'services']
            )
        )        
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.MAIN_ROAD_INPUT,
                self.tr('Слой с главными дорогами'),
                types=[QgsProcessing.TypeVectorLine],
                defaultValue='main_route'
            )
        )    
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.SECONDARY_ROAD_INPUT,
                self.tr('Слой с доп. дорогами'),
                types=[QgsProcessing.TypeVectorLine],
                defaultValue='secondary_routes'
                
            )
        )    
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.HEIGHTS_INPUT,
                self.tr('Слой с картой высот рельефа'),
                optional=True,
            )
        )    
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.PATHS_OUTPUT,
                self.tr('Итоговый слой с кратчайшими путями'),
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
        sign_layer = self.parameterAsLayer(parameters, self.SIGN_INPUT, context)
        main_road_layer = self.parameterAsLayer(parameters, self.MAIN_ROAD_INPUT, context)
        secondary_road_layer = self.parameterAsLayer(parameters, self.SECONDARY_ROAD_INPUT, context)
        poi_layers = self.parameterAsLayerList(parameters, self.POIS_INPUT, context)
        height_layer = self.parameterAsRasterLayer(parameters, self.HEIGHTS_INPUT, context)
        tolerance = self.parameterAsDouble(parameters, self.TOLERANCE, context)
        
        framework = DistanceCalculateFramework(
            sign_layer, 
            poi_layers, 
            main_road_layer, 
            secondary_road_layer, 
            height_layer, 
            tolerance,
            feedback
            )
        
        path_sink, path_dest_id = self.parameterAsSink(parameters, self.PATHS_OUTPUT,
                context, framework.output_fields, QgsWkbTypes.LineString, framework.TARGET_CRS)
        
        for i, path_feature in enumerate(framework.main()):
            path_feature['id'] = i
            path_sink.addFeature(path_feature, QgsFeatureSink.FastInsert)
        return {self.PATHS_OUTPUT: path_dest_id}
        
    

    def name(self):
        return 'distance_calculate'

    def displayName(self):
        return 'Расчет расстояний'

    def group(self):
        return 'Веломаршрут'

    def groupId(self):
        return 'Group1'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return DistanceCalculateAlgorithm()

    def shortHelpString(self):
        return "<b>Параметры</b><ul>"\
                "<li><b>Слой с носителями</b> - слой, от объектов которого будут "\
                "начинаться расчеты кратчайших путей</li>"\
                "<li><b>Слой с объектами</b> - слои, в которых будут искаться объекты "\
                "по названию и до которых будет считаться маршрут (в том числе сервисы)</li>"\
                "<li><b>Слой с главными дорогами</b> - основной маршрут сети передвижения, "\
                "в котором обозначены коды участков</li>"\
                "<li><b>Слой с доп.дорогами</b> - слой, в котором обозначены второстепенные "\
                "участки дороги, также используется для построение сети передвижения</li>"\
                "<li><b>Слой с картой высот рельефа</b> - растровый слой, в котором значение пикселя "\
                "соответствует высоте рельефа от уровня моря (с сайта USGS Earthexplorer, алгоритм mean)</li>"\
                "<li><b>Topology tolerance</b> - степень “сшивания” дорожной сети. Если все "\
                "сопряжения всех участков лежат точно на полилиниях, то значения оставить как 0</li>"\
                "</ul>"\
                "<b>Результат</b><ul>"\
                "<li>Будет создан слой с линиями кратчайших путей. Он поможет отслеживать "\
                "корректность работы алгоритма, а также посмотреть рассчитанные длины путей (2d - без учета рельефа, 3d - с учетом)</li>"\
                "<li>В аттрибутивке слоя носителей обновятся значения для параметров типа: "\
                "PIC, km, NameEn, а так же присвоен код ближайшего участка</li>"\
                "</ul>"