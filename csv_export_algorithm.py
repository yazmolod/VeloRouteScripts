# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import QCoreApplication
import re
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterEnum,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterFile,
    QgsProcessingParameterMultipleLayers,
    QgsProcessing,
    QgsProject,
    QgsProcessingException,
    )

from pathlib import Path
from datetime import datetime
import re
import csv
from VeloRouteScripts import utils

class CsvExportAlgorithm(QgsProcessingAlgorithm):
    PARAM_EXPORT_LAYERS = 'PARAM_EXPORT_LAYERS'
    PARAM_CONVERT_TO_PIC = 'PARAM_CONVERT_TO_PIC'
    PARAM_PIC_FILEPATH = 'PARAM_PIC_FILEPATH'
    PARAM_ROUTECODE_ENUM = 'PARAM_ROUTECODE_ENUM'
    
    # def __init__(self, routes, *args, **kwargs):
    #     super().__init__(*args, **kwargs)
    #     self.routes = routes
    
    def initAlgorithm(self, config):
        self.project_instance = QgsProject.instance()
        self.project_folder = Path(self.project_instance.homePath())
        self.route_codes = utils.get_route_codes()
        
        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                self.PARAM_EXPORT_LAYERS,
                self.tr('Экспортируемые слои'),
                QgsProcessing.TypeVectorPoint
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.PARAM_ROUTECODE_ENUM, 
                self.tr('Код участка'), 
                options = self.route_codes,
                defaultValue=0,
                )
            )
        
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.PARAM_CONVERT_TO_PIC, 
                self.tr('Автозамена на пиктограммы'), 
                defaultValue=False, 
                )
            )
        self.addParameter(
            QgsProcessingParameterFile(
                self.PARAM_PIC_FILEPATH,
                self.tr('Файл с таблицей пиктограмм'),
                extension='csv', 
                optional = True,
                defaultValue=str(self.find_pic_table())
                )
            )

    def processAlgorithm(self, parameters, context, feedback):
        self.feedback = feedback
        
        export_layers = self.parameterAsLayerList(parameters, self.PARAM_EXPORT_LAYERS, context)
        convert_to_pic = self.parameterAsBool(parameters, self.PARAM_CONVERT_TO_PIC, context)
        pic_filepath = self.parameterAsFile(parameters, self.PARAM_PIC_FILEPATH, context)
        route_code_enum = self.parameterAsEnum(parameters, self.PARAM_ROUTECODE_ENUM, context)
        
        route_code = self.route_codes[route_code_enum]
        self.pic_replace_table = self.load_pic_replace_table(pic_filepath)
        
        infoplan_folder = self.project_folder / 'Инфоплан'
        infoplan_folder.mkdir(exist_ok=True)        
        self.export_folder = infoplan_folder / '{}_{}'.format(route_code, datetime.now().strftime('%d-%m-%Y_%H-%M'))
        self.export_folder.mkdir(exist_ok=True)
        
        feedback.setProgress(0)
        for im, map_layer in enumerate(export_layers):
            if feedback.isCanceled():
                break
            try:      
                self.export_layer(map_layer, route_code, convert_to_pic)
                feedback.pushInfo('Successfully exported layer {}'.format(map_layer.name()))
            except Exception as e:
                feedback.reportError('Failed to export layer {}'.format(map_layer.name()))
            finally:
                feedback.setProgress(int((im+1)/len(export_layers)*100))
        return {}

    def name(self):
        return 'csv_export'

    def displayName(self):
        return 'Экспорт CSV'

    def group(self):
        return 'Веломаршрут'

    def groupId(self):
        return 'Group1'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return CsvExportAlgorithm()
    
    ### CUSTOM ###
    
    def load_pic_replace_table(self, path):
        with open(path, 'r') as file:
            reader = csv.reader(file, delimiter=',')
            result = dict(reader)
        return result
    
    def is_export_layer(self, map_name):
        pat = re.compile(r'\d+_[A-Z]+')
        return pat.fullmatch(map_name) is not None
    
    def find_pic_table(self):
        for p in self.project_folder.glob('**/*.csv'):
            if 'pic' in p.name:
                return p
        return self.project_folder
    
    def replace_pics(self, attributes):
        replaced_attributes = attributes[:]
        for i,v in enumerate(replaced_attributes):
            if v in self.pic_replace_table:
                replaced_attributes[i] = self.pic_replace_table[v]
        return replaced_attributes
    
    def export_layer(self, map_layer, route_code, autoreplace:bool):
        headers = [i.name() for i in map_layer.fields()]
        if 'routcode' not in [i.name() for i in map_layer.fields()]:
            self.feedback.reportError('Layer should contain field "routcode"')
            raise QgsProcessingException('Layer should contain field "routcode"')
        else:
            attributes_list = [i.attributes() for i in map_layer.getFeatures() if i['routcode'] == route_code]
            if attributes_list:
                export_file = self.export_folder / '{} {}.csv'.format(map_layer.name(), route_code)
                with open(export_file, 'w', newline='', encoding='utf-16') as file:
                    writer = csv.writer(file, delimiter=',')
                    writer.writerow(headers)
                    for attribute_line in attributes_list:
                        if autoreplace:
                            attribute_line = self.replace_pics(attribute_line)
                        writer.writerow(attribute_line)
            else:
                self.feedback.pushInfo(f'Theres no routcode {route_code} in layer {map_layer.name()}')