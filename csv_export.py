from pathlib import Path
from datetime import datetime
import re
import csv

def load_pic_replace_table(path):
    with open(path, 'r') as file:
        reader = csv.reader(file, delimiter=',')
        result = dict(reader)
    return result

def is_export_layer(map_name):
    pat = re.compile(r'\d+_[A-Z]+')
    return pat.fullmatch(map_name) is not None

def replace_pics(attributes):
    replaced_attributes = attributes[:]
    for i,v in enumerate(replaced_attributes):
        if v in pic_replace_table:
            replaced_attributes[i] = pic_replace_table[v]
    return replaced_attributes

def export_layer(map_layer, autoreplace:bool):
    headers = [i.name() for i in map_layer.fields()]
    attributes_list = [i.attributes() for i in map_layer.getFeatures()]
    export_file = export_folder / (map_layer.name() + '.csv')
    with open(export_file, 'w', newline='', encoding='utf-16') as file:
        writer = csv.writer(file, delimiter=',')
        writer.writerow(headers)
        for attribute_line in attributes_list:
            if autoreplace:
                attribute_line = replace_pics(attribute_line)
            writer.writerow(attribute_line)

project_instance= QgsProject.instance()
project_folder = project_instance.homePath()
infoplan_folder = Path(project_folder) / 'Инфоплан'
infoplan_folder.mkdir(exist_ok=True)

export_folder = infoplan_folder / datetime.now().strftime('%d-%m-%Y_%H-%M')
export_folder.mkdir(exist_ok=True)

pic_replace_table = load_pic_replace_table(r"D:\Yandex\YandexDisk\freelance\плагин qgis\QGIS_deploy_prototype\QGIS_deploy_prototype\pic_list\pic_autochange_list.csv")

for map_layer in project_instance.mapLayers().values():
    if is_export_layer(map_layer.name()):
        export_layer(map_layer,True)