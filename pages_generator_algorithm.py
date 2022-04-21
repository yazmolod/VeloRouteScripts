# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import QCoreApplication
import re
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterEnum,
    QgsProject,
    QgsProcessingParameterEnum,
    QgsProcessingParameterMultipleLayers,
    QgsProcessing,
    QgsProcessingParameterString,
    QgsProcessingParameterFile,
    QgsProcessingParameterDefinition
    )
from VeloRouteScripts import utils
from .pages_framework import PageGeneratorFramework
from pathlib import Path

def get_layout_names():
    if QgsProject.instance() and QgsProject.instance().layoutManager():
        return [i.name() for i in QgsProject.instance().layoutManager().layouts()]
    else:
        return []

class PagesExporterAlgorithm(QgsProcessingAlgorithm):
    PARAM_EXPORT_LAYOUTS_ENUMS = 'PARAM_EXPORT_LAYOUTS'
    PARAM_EXPORT_LAYERS = 'PARAM_EXPORT_LAYERS'

    def initAlgorithm(self, config):
        self.layout_names = get_layout_names()
        self.addParameter(
            QgsProcessingParameterEnum(
                self.PARAM_EXPORT_LAYOUTS_ENUMS, 
                self.tr('Листы для экспорта'), 
                options = self.layout_names,
                allowMultiple = True,
                )
            )
        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                self.PARAM_EXPORT_LAYERS,
                self.tr('Cлои для генерации'),
                QgsProcessing.TypeVectorPoint,
                defaultValue = '123_DIR'
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        export_layers = self.parameterAsLayerList(parameters, self.PARAM_EXPORT_LAYERS, context)
        layout_enums = self.parameterAsEnums(parameters, self.PARAM_EXPORT_LAYOUTS_ENUMS, context)
        layout_names = [self.layout_names[i] for i in layout_enums]
        framework = PageGeneratorFramework(
            feedback,
            export_layers,
            )
        framework.export_layouts_by_names(layout_names)
        return {}

    def name(self):
        return 'Экспорт PDF'

    def displayName(self):
        return self.tr(self.name())

    def group(self):
        return 'Веломаршрут'

    def groupId(self):
        return 'Group1'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return PagesExporterAlgorithm()
    

class PagesGeneratorAlgorithm(QgsProcessingAlgorithm):
    PARAM_ROUTECODE_ENUMS = 'PARAM_ROUTECODE_ENUMS'
    PARAM_LAYOUT_NAME_ENUM = 'PARAM_LAYOUT_NAME_ENUM'
    PARAM_EXPORT_LAYERS = 'PARAM_EXPORT_LAYERS'
    PARAM_ITEM_ID_PLACE_MAP = 'PARAM_ITEM_ID_PLACE_MAP'
    PARAM_ITEM_ID_GENERAL_MAP = 'PARAM_ITEM_ID_GENERAL_MAP'
    PARAM_ITEM_ID_DATA_TABLE = 'PARAM_ITEM_ID_DATA_TABLE'
    PARAM_ITEM_ID_WF_PIC = 'PARAM_ITEM_ID_WF_PIC'
    PARAM_ITEM_PAGE_LABEL = 'PARAM_ITEM_PAGE_LABEL'
    PARAM_ITEM_COORDS_LABEL = 'PARAM_ITEM_COORDS_LABEL'
    PARAM_WF_TYPES_FOLDER = 'PARAM_WF_TYPES_FOLDER'
    PARAM_ITEM_ROUTE_LABEL = 'PARAM_ITEM_ROUTE_LABEL'

    
    def initAlgorithm(self, config):
        self.project_instance = QgsProject.instance()
        self.project_folder = Path(self.project_instance.homePath())
        self.route_codes = utils.get_route_codes()
        self.layout_names = get_layout_names()
        
        self.addParameter(
            QgsProcessingParameterEnum(
                self.PARAM_ROUTECODE_ENUMS, 
                self.tr('Коды участков'), 
                options = self.route_codes,
                allowMultiple = True,
                defaultValue = 'Y-K'
                )
            )
        
        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                self.PARAM_EXPORT_LAYERS,
                self.tr('Cлои для генерации'),
                QgsProcessing.TypeVectorPoint,
                defaultValue = '123_DIR'
            )
        )
        
        self.addParameter(
            QgsProcessingParameterEnum(
                self.PARAM_LAYOUT_NAME_ENUM, 
                self.tr('Названия шаблона макета'), 
                options = self.layout_names,
                defaultValue = 0,
                )
            )
        self.addParameter(
            QgsProcessingParameterFile(
                self.PARAM_WF_TYPES_FOLDER,
                self.tr('Папка с картинками общих видов носителей'),
                defaultValue = str(self.find_wf_folder()),
                behavior = QgsProcessingParameterFile.Folder
                )
            )
        advanced_params = []
        advanced_params.append(
            QgsProcessingParameterString(self.PARAM_ITEM_ID_PLACE_MAP,
                                       self.tr('ID детализированного расположения носителя'),
                                       defaultValue='place_map_id'
                                       )
            )
        advanced_params.append(
            QgsProcessingParameterString(self.PARAM_ITEM_ID_GENERAL_MAP,
                                       self.tr('ID общего расположения носителя'),
                                       defaultValue='general_map_id'
                                       )
            )
        advanced_params.append(
            QgsProcessingParameterString(self.PARAM_ITEM_ID_DATA_TABLE,
                                       self.tr('ID таблицы инфоплана'),
                                       defaultValue='data_table_id'
                                       )
            )
        advanced_params.append(
            QgsProcessingParameterString(self.PARAM_ITEM_PAGE_LABEL,
                                       self.tr('ID метки страницы'),
                                       defaultValue='page_label_id'
                                       )
            )
        advanced_params.append(
            QgsProcessingParameterString(self.PARAM_ITEM_COORDS_LABEL,
                                       self.tr('ID метки координат'),
                                       defaultValue='coords_label_id'
                                       )
            )
        advanced_params.append(
            QgsProcessingParameterString(self.PARAM_ITEM_ROUTE_LABEL,
                                       self.tr('ID метки названия маршрута'),
                                       defaultValue='route_label_id'
                                       )
            )
        advanced_params.append(
            QgsProcessingParameterString(self.PARAM_ITEM_ID_WF_PIC,
                                       self.tr('ID общего вида носителя'),
                                       defaultValue='wf_pic_id'
                                       )
            )
        
        for p in advanced_params:
            p.setFlags(p.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
            self.addParameter(p)


    def processAlgorithm(self, parameters, context, feedback):
        logger = utils.FeedbackLogger(__name__, feedback)
        logger.log_info('Analyze parameters')
        routecode_enums = self.parameterAsEnums(parameters, self.PARAM_ROUTECODE_ENUMS, context)
        routecodes = [self.route_codes[i] for i in routecode_enums]
        layout_enum = self.parameterAsEnum(parameters, self.PARAM_LAYOUT_NAME_ENUM, context)
        layout_name = self.layout_names[layout_enum]
        export_layers = self.parameterAsLayerList(parameters, self.PARAM_EXPORT_LAYERS, context)
        wf_types_folder = self.parameterAsFile(parameters, self.PARAM_WF_TYPES_FOLDER, context)
        coords_label_id = self.parameterAsString(parameters, self.PARAM_ITEM_COORDS_LABEL, context)
        route_label_id = self.parameterAsString(parameters, self.PARAM_ITEM_ROUTE_LABEL, context)
        page_label_id = self.parameterAsString(parameters, self.PARAM_ITEM_PAGE_LABEL, context)
        place_map_id = self.parameterAsString(parameters, self.PARAM_ITEM_ID_PLACE_MAP, context)
        general_map_id = self.parameterAsString(parameters, self.PARAM_ITEM_ID_GENERAL_MAP, context)
        data_table_id = self.parameterAsString(parameters, self.PARAM_ITEM_ID_DATA_TABLE, context)
        wf_pic_id = self.parameterAsString(parameters, self.PARAM_ITEM_ID_WF_PIC, context)
        
        
        framework = PageGeneratorFramework(
            feedback,
            export_layers, 
            routecodes,
            layout_name, 
            wf_types_folder,
            coords_label_id,
            page_label_id,
            route_label_id,
            place_map_id,
            general_map_id,
            data_table_id,
            wf_pic_id,
            )
        logger.log_info('Start framework')
        layouts = framework.generate_layouts()
        # framework.export_layouts(layouts)
        return {}

    def name(self):
        return 'Генератор PDF'

    def displayName(self):
        return self.tr(self.name())

    def group(self):
        return 'Веломаршрут'

    def groupId(self):
        return 'Group1'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return PagesGeneratorAlgorithm()
    
    ### CUSTOM ###
    
    def find_wf_folder(self):
        for p in self.project_folder.glob('**/*'):
            if p.is_dir() and 'wf' in p.name:
                return p
        return self.project_folder
        