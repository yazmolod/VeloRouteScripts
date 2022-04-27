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
    QgsProcessingParameterDefinition,
    QgsProcessingParameterBoolean
    )
from VeloRouteScripts import utils
from VeloRouteScripts.pages_framework import PageGeneratorFramework
from pathlib import Path

def get_layout_names():
    if QgsProject.instance() and QgsProject.instance().layoutManager():
        return [i.name() for i in QgsProject.instance().layoutManager().layouts()]
    else:
        return []

class PagesExporterAlgorithm(QgsProcessingAlgorithm):
    PARAM_EXPORT_LAYOUTS_ENUMS = 'PARAM_EXPORT_LAYOUTS'
    PARAM_EXPORT_LAYERS = 'PARAM_EXPORT_LAYERS'
    PARAM_DEL_LAYOUT = 'PARAM_DEL_LAYOUT'

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
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.PARAM_DEL_LAYOUT,
                self.tr('Удалять макет после экспорта'),
                defaultValue=False, 
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        utils.save_project()
        del_layout = self.parameterAsBool(parameters, self.PARAM_DEL_LAYOUT, context)
        export_layers = self.parameterAsLayerList(parameters, self.PARAM_EXPORT_LAYERS, context)
        layout_enums = self.parameterAsEnums(parameters, self.PARAM_EXPORT_LAYOUTS_ENUMS, context)
        layout_names = [self.layout_names[i] for i in layout_enums]
        framework = PageGeneratorFramework(
            feedback,
            export_layers,
            )
        framework.export_layouts_by_names(layout_names, del_layout)
        return {}

    def name(self):
        return 'Листы: экспорт PDF'

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
    
    def shortHelpString(self):
        return '<b>Принцип работы</b><br>'\
                'Алгоритм проходится по каждому макеты, выключает видимость всех '\
                'носителей кроме того, который привязан к данному макету, и экспортирует в сгенерированную папку pdf<br><br>'\
                '<b>ВАЖНО</b><br>'\
                'Основная причина, почему экспорт был вынесен в отдельный алгоритм - '\
                'нестабильность работы экспорта в QGIS. Иногда листы экспортируется сразу все и '\
                'без проблем, но чаще всего программа просто крашится. Поэтому '\
                '<b>алгоритм сохраняет проект в начале работы.</b> Возможно, экспортировать все листы придется в несколько заходов<br><br>'\
                '<b>Параметры</b><ul>'\
                '<li><b>Листы для экспорта</b> - выбираем созданные алгоритмом генерации листов макеты</li>'\
                '<li><b>Слои для генерации</b> - здесь следует выбрать абсолютно все слои, которые не должны отображаться целиком на листе</li>'\
                '<li><b>Удалять макет после экспорта</b> - при успешном экспорте макет будет удален из проекта</li>'\
                '</ul>'\
                '<b>Результат</b><ul>'\
                '<li>Создастся папка типа pdf/дата выгрузки, в которой будут созданы pdf файлы. Имена pdf файлов соответствуют их номеру</li>'\
                '</ul>'
    

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
                self.tr('Cлои носителей для генерации'),
                QgsProcessing.TypeVectorPoint,
                defaultValue = '123_DIR'
            )
        )
        
        self.addParameter(
            QgsProcessingParameterEnum(
                self.PARAM_LAYOUT_NAME_ENUM, 
                self.tr('Название шаблона макета'), 
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
        return {}

    def name(self):
        return 'Листы: генерация'

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
    
    def shortHelpString(self):
        return '<b>Принцип работы</b><br>'\
                'Данный алгоритм позволяет на основании макета-шаблона сгенерировать '\
                'макеты с обновленными отображениями объекта и информацией по нему. '\
                'Порядок сгенерированных макетов базируется на географическом положении носителя<br><br>'\
                '<b>Параметры</b><ul>'\
                '<li><b>Коды участков</b> - для объектов с каким кодов нужно сгенерировать макеты. Значения берутся из слоя с именем типа “main_route”</li>'\
                '<li><b>Слои носителей для генерации</b> - на объектов этих слоев будут сгенерированы макеты '\
                '(если код объекта присутствует в кодах требуемых участков)</li>'\
                '<li><b>Название шаблона макета</b> - на основании этого макета будут сгенерированы новые макеты</li>'\
                '<li>Папка с картинками общих видов носителей - папка, в которой содержатся изображения с видами носителей. '\
                'Ищется автоматически в папке проекта по содержанию в названии “wf”</li>'\
                '<li><b>Перечень параметров ID</b> - в них зафиксированы id элементов макета, '\
                'которые подлежат обновлению для каждого конкретного объекта. Для удобства '\
                '(чтобы каждый раз не заполнять самостоятельно) рекомендуется сохранить дефолтные значения '\
                'и проследить, чтобы в макеты они были названы именно так</li>'\
                '</ul>'\
                '<b>Результат</b><ul>'\
                '<li>Будут сгенерированы макеты с именем типа “Layout N”, '\
                'в которых будут обновлены данные для конкретного носителя и зафиксированы данные для экспорта</li>'\
                '</ul>'
    
    ### CUSTOM ###
    
    def find_wf_folder(self):
        for p in self.project_folder.glob('**/*'):
            if p.is_dir() and 'wf' in p.name:
                return p
        return self.project_folder
        