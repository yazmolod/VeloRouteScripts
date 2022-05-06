# -*- coding: utf-8 -*-
from pathlib import Path
from datetime import datetime
from qgis._core import (
    QgsRectangle,
    QgsProject,
    QgsLayoutExporter,
    QgsGeometry,
    QgsPointXY,
    QgsCoordinateReferenceSystem,
    QgsExpressionContextUtils,
    QgsRenderContext,
    )
from VeloRouteScripts import utils
import time
import os



class PageGeneratorFramework:    
    nonprint_table_columns = ['id', 'num', 'type', 'routcode', 'degree']    
    id_field = 'id'
    feature_route_code_field = 'routcode'
    road_route_code_field = 'CODE'   
    
    def __init__(self, 
                feedback,
                export_layers, 
                export_route_codes=None,
                reference_layout_name=None,
                wf_types_folder=None,
                coords_label_id=None,
                page_label_id=None,
                route_label_id=None,
                place_map_id=None,
                general_map_id=None,
                data_table_id=None,
                wf_pic_id=None,
                ):
        self.feedback = feedback
        self.logger = utils.FeedbackLogger(__name__, self.feedback)
        self.logger.log_debug('Init...')
        self.project = QgsProject.instance()
        self.lay_mng = self.project.layoutManager()
        self.reference_layout = self.lay_mng.layoutByName(reference_layout_name)
        self.layers = export_layers
        self.route_codes = export_route_codes
        self.current_feature = None
        self.current_layer = None
        self.current_page = None
        self.road_layer = utils.get_main_road_layer()
        self.general_map_margin = 0.05
        self.wf_types_folder = wf_types_folder
        # items which we modify
        self.coords_label_id = coords_label_id
        self.page_label_id = page_label_id
        self.route_label_id = route_label_id
        self.place_map_id = place_map_id
        self.general_map_id = general_map_id
        self.data_table_id = data_table_id
        self.wf_pic_id = wf_pic_id
        

        
    def get_layout_item(self, layout, item_id):
        item = layout.itemById(item_id)
        if item is None:
            raise Exception('Item {} was not found'.format(item_id))
        else:
            return item
        
    def get_pdf_settings(self):
        settings = QgsLayoutExporter.PdfExportSettings()
        # settings.forceVectorOutput = False
        settings.exportMetadata = False
        settings.textRenderFormat = QgsRenderContext.TextFormatAlwaysOutlines
        settings.appendGeoreference = False 
        settings.includeGeoPdfFeatures = False
        # settings.rasterizeWholeImage = True
        return settings

    def export(self, folder, layout, page):
        filepath = Path(folder, '%05d.pdf' % int(page))
        self.logger.log_info(f'File {filepath} saving...')
        settings = self.get_pdf_settings()
        exporter = QgsLayoutExporter(layout)
        status = exporter.exportToPdf(str(filepath), settings)
        self.logger.log_info(f'Export status {status}')
        
        
    def duplicate_reference_layout(self):
        self.logger.log_debug('Duplicate layout')
        new_name = self.lay_mng.generateUniqueTitle()
        return self.lay_mng.duplicateLayout(self.reference_layout, new_name)
    
    def remove_layout(self, layout):
        self.logger.log_debug('Remove layout {layout.name()}')
        return self.lay_mng.removeLayout(layout)
    
    def generate_export_folder(self):
        project_folder = Path(self.project.homePath())
        layout_folder = project_folder / 'pdf' / '{}'.format(
            datetime.now().strftime('%d%m%Y_%H-%M')
            )
        layout_folder.mkdir(parents=True, exist_ok=True)
        return layout_folder
  
    def recenter_main_map(self, layout):
        self.logger.log_info('Recenter place map...')
        map_item = self.get_layout_item(layout, self.place_map_id)
        map_scale = map_item.scale()
        map_crs = map_item.crs()
        pt = self.get_transformed_current_point(map_crs)
        new_extent = QgsRectangle.fromCenterAndSize(pt, 1, 1)
        map_item.zoomToExtent(new_extent)
        map_item.setScale(map_scale)
        self.logger.log_info('DONE')
        
    def extent_general_map(self, layout):
        self.logger.log_info('Extent general map...')
        map_item = self.get_layout_item(layout, self.general_map_id)
        map_crs = map_item.crs()
        field_names = [i.name() for i in self.current_feature.fields()]
        if self.feature_route_code_field not in field_names:
            raise Exception(f'Cant find attribute {self.feature_route_code_field} in layer {self.current_layer.name()}')
        else:
            road_code = self.current_feature[self.feature_route_code_field]
            minx,miny,maxx,maxy = self.get_road_extent(road_code)
            min_pt = QgsGeometry.fromPointXY(QgsPointXY(minx, miny))
            max_pt = QgsGeometry.fromPointXY(QgsPointXY(maxx, maxy))
            min_pt = utils.xform_geometry(min_pt, self.road_layer.sourceCrs(), map_crs)
            max_pt = utils.xform_geometry(max_pt, self.road_layer.sourceCrs(), map_crs)
            new_extent = QgsRectangle(min_pt.asPoint(), max_pt.asPoint())
            #add margin
            ymargin = new_extent.height()*self.general_map_margin
            xmargin = new_extent.height()*self.general_map_margin
            new_extent.setXMinimum(new_extent.xMinimum() - xmargin)
            new_extent.setYMinimum(new_extent.yMinimum() - ymargin)
            new_extent.setXMaximum(new_extent.xMaximum() + xmargin)
            new_extent.setYMaximum(new_extent.yMaximum() + ymargin)
            map_item.zoomToExtent(new_extent)
            self.logger.log_info('DONE')
        
        
    def get_road_extent(self, road_code):
        result_bbox = None
        for road_feature in self.road_layer.getFeatures():
            if road_feature[self.road_route_code_field] == road_code:
                bbox = road_feature.geometry().boundingBox()
                if result_bbox is None:
                    result_bbox = bbox
                else:
                    result_bbox.combineExtentWith(bbox)
        if result_bbox is None:
            raise Exception(f'Not found roads with code {road_code}')
        else:            
            return result_bbox.xMinimum(), result_bbox.yMinimum(), result_bbox.xMaximum(), result_bbox.yMaximum()
        
    def change_picture(self, layout):
        self.logger.log_info('Change wf pic...')
        pic_item = self.get_layout_item(layout, self.wf_pic_id)
        pic_path = os.path.join(self.wf_types_folder, self.current_layer.name() + '.jpg')
        if os.path.exists(pic_path):
            pic_item.setPicturePath(str(pic_path))
        else:
            raise Exception(f'Path {pic_path} not found!')
        self.logger.log_info('DONE')
        
    def update_labels(self, layout):
        self.logger.log_info('Update labels...')
        pt = self.get_transformed_current_point(QgsCoordinateReferenceSystem("EPSG:4326"))
        self.get_layout_item(layout, self.page_label_id).setText('стр ' + str(self.current_page))
        self.get_layout_item(layout, self.coords_label_id).setText('%.6f, %.6f'% (pt.x(), pt.y()))
        self.get_layout_item(layout, self.route_label_id).setText('Участок %s' % self.current_feature[self.feature_route_code_field])
        self.logger.log_info('DONE')
        
    def turn_on_all_features(self):
        self.logger.log_debug('Turn on layers')
        for layer in self.layers:
            layer.setSubsetString('')
        
    def turn_off_all_features(self):
        self.logger.log_debug('Turn off layers')
        for layer in self.layers:
            layer.setSubsetString('{}=-1'.format(self.id_field))
        
    def iter_ordered_features(self):
        self.turn_on_all_features()
        for road_packed_feature, pt_packed_feature in utils.iter_points_along_road(self.road_layer, self.layers, self.feedback):
            if pt_packed_feature.feature[self.feature_route_code_field] in self.route_codes:                
                yield pt_packed_feature
                     
    def get_transformed_current_point(self, target_crs):
        geometry = self.current_feature.geometry()
        geometry = utils.xform_geometry(geometry, self.current_layer.sourceCrs(), target_crs)
        return geometry.asPoint()
        
    def generate_table(self, layout):
        self.logger.log_info('Update data table...')
        table_item = self.get_layout_item(layout, self.data_table_id).multiFrame()
        feature_fields = [i.name() for i in self.current_feature.fields()]
        feature_attributes = self.current_feature.attributes()
        trs = []
        for k,v in zip(feature_fields, feature_attributes):
            if k.lower() not in self.nonprint_table_columns:
                trs.append(f'<tr><td>{k}</td><td>{v}</td></tr>')
        html_table = f'<table><thead><tr><th>Инфоплан</th><th></th></tr></thead><tbody>{"".join(trs)}</tbody></table>'
        table_item.setHtml(html_table)
        # программа крашится
        # table_item.loadHtml()
        self.logger.log_info('DONE')
        
    def update_layout(self, layout):
        self.logger.log_debug('Update layout')
        funcs = [
            self.recenter_main_map,
            self.extent_general_map,
            self.change_picture,
            self.generate_table,
            self.update_labels
                ]
        for f in funcs:
            try:
                f(layout)
            except Exception as e:
                self.logger.log_error(f'ERROR on {f.__name__}: {e}')
            
        
    def generate_id(self):
        self.logger.log_debug('Generate id')
        self.turn_on_all_features()
        for layer in self.layers:
            layer.startEditing()
            for i,feature in enumerate(layer.getFeatures()):
                feature.setAttribute(self.id_field, i+1)
                layer.updateFeature(feature)
            layer.commitChanges()
    
    def generate_layouts(self):
        self.generate_id()
        export_folder = self.generate_export_folder()      
        self.current_page = 1
        layouts = []
        for pt_packed_feature in self.iter_ordered_features():
            if self.feedback.isCanceled():
                break
            else:
                layer = pt_packed_feature.layer
                feature = pt_packed_feature.feature
                self.logger.log_info(f'Generating layout: layer = {layer.name()}, feature_id = {feature[self.id_field]}')
                self.current_feature = feature
                self.current_layer = layer
                layout = self.duplicate_reference_layout()
                self.update_layout(layout)
                # сохраняем переменные для экспорта
                layout_variables = {
                    'export_layer_id': layer.id(),
                    'export_feature_id': feature[self.id_field],
                    'export_page': self.current_page,
                    'export_folder': str(export_folder),
                }
                QgsExpressionContextUtils.setLayoutVariables(layout, layout_variables)
                layouts.append(layout)
                self.current_page += 1
        utils.save_project()
        return layouts
    
    def export_layouts_by_names(self, layout_names, del_layout=False):
        layouts = [self.lay_mng.layoutByName(i) for i in layout_names]
        return self.export_layouts(layouts, del_layout=del_layout)
    
    def export_layouts(self, layouts, del_layout=False):
        self.turn_off_all_features()
        for layout in layouts:
            if self.feedback.isCanceled():
                break
            else:
                layout_scope = layout.createExpressionContext()
                layer_id = layout_scope.variable('export_layer_id')
                feature_id = layout_scope.variable('export_feature_id')
                page = layout_scope.variable('export_page')
                folder = layout_scope.variable('export_folder')
                if not layer_id or not feature_id or not page:
                    self.logger.log_error("Can't find custom property for layer or feature")
                else:
                    self.logger.log_info(f'Export layout: layer_id = {layer_id}, feature_id = {feature_id}')
                    layer = self.project.mapLayer(layer_id)
                    layer.setSubsetString('{}={}'.format(self.id_field, feature_id))
                    self.export(folder, layout, page)
                    if del_layout:
                        self.remove_layout(layout)
                        utils.save_project()
                    layer.setSubsetString('{}=-1'.format(self.id_field))
        self.turn_on_all_features()
        del self.logger


