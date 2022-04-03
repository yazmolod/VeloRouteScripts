from pathlib import Path
from datetime import datetime
from qgis._core import QgsRectangle
from utils import FeedbackImitator, xform_geometry



class PageGeneratorFramework:
    
    id_field = 'id'
    coords_label_id = 'COORDS_LABEL'
    page_label_id = 'PAGE_LABEL'
    wf_types_folder = 'wf_type_previews'
    layout_template_name = 'test'
    main_map_id = 'Map 1'
    general_map_id = 'Map 2'
    pic_id = 'wf_type'
    feature_route_code_field = 'routcode'
    road_route_code_field = 'CODE'
    table_id = 'data_table'
    nonprint_columns = ['id', 'Num', 'type',]
    
    def __init__(self):
        self.project = QgsProject.instance()
        self.lay_mng = self.project.layoutManager()
        self.layout = self.lay_mng.layoutByName(self.layout_template_name)
        self.layers = self.project.mapLayersByName('123_DIR') + self.project.mapLayersByName('201_SIGN') 
        self.current_feature = None
        self.current_layer = None
        self.current_page = None
        self.feedback = FeedbackImitator()
        self.road_layer = self.project.mapLayersByName('main_route_UTF-8')[0]
        self.general_map_margin = 0.05

    def export(self, folder):
        filepath = folder / ('%05d.pdf' % self.current_page)
        settings = QgsLayoutExporter.PdfExportSettings()
        exporter = QgsLayoutExporter(self.layout)
        status = exporter.exportToPdf(str(filepath), settings)
        self.feedback.pushInfo(f'[] File {filepath} saved')
    
    def generate_export_folder(self):
        project_folder = Path(self.project.homePath())
        layout_folder = project_folder / 'pdf' / datetime.now().strftime('%d%m%Y_%H-%M')
        layout_folder.mkdir(parents=True, exist_ok=True)
        return layout_folder
  
    def recenter_main_map(self):
        map_item = self.layout.itemById(self.main_map_id)
        map_scale = map_item.scale()
        map_crs = map_item.crs()
        pt = self.get_transformed_current_point(map_crs)
        new_extent = QgsRectangle.fromCenterAndSize(pt, 1, 1)
        map_item.zoomToExtent(new_extent)
        map_item.setScale(map_scale)
        
    def extent_general_map(self):
        map_item = self.layout.itemById(self.general_map_id)
        map_crs = map_item.crs()
        field_names = [i.name() for i in self.current_feature.fields()]
        if self.feature_route_code_field not in field_names:
            raise Exception(f'Cant find attribute {self.feature_route_code_field} in layer {self.current_layer.name()}')
        else:
            road_code = self.current_feature[self.feature_route_code_field]
            minx,miny,maxx,maxy = self.get_road_extent(road_code)
            min_pt = QgsGeometry.fromPointXY(QgsPointXY(minx, miny))
            max_pt = QgsGeometry.fromPointXY(QgsPointXY(maxx, maxy))
            min_pt = xform_geometry(min_pt, self.road_layer.sourceCrs(), map_crs)
            max_pt = xform_geometry(max_pt, self.road_layer.sourceCrs(), map_crs)
            new_extent = QgsRectangle(min_pt.asPoint(), max_pt.asPoint())
            #add margin
            ymargin = new_extent.height()*self.general_map_margin
            xmargin = new_extent.height()*self.general_map_margin
            new_extent.setXMinimum(new_extent.xMinimum() - xmargin)
            new_extent.setYMinimum(new_extent.yMinimum() - ymargin)
            new_extent.setXMaximum(new_extent.xMaximum() + xmargin)
            new_extent.setYMaximum(new_extent.yMaximum() + ymargin)
            map_item.zoomToExtent(new_extent)
        
        
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
        
    def change_picture(self):
        pic_item = self.layout.itemById(self.pic_id)
        pic_path = Path(pic_item.picturePath())
        if pic_path.stem != self.current_layer.name():
            new_path = pic_path.parent / (self.current_layer.name() + '.jpg')
            if new_path.exists():
                pic_item.setPicturePath(str(new_path))
            else:
                raise Exception(f'Path {new_path} not found!')
        
    def update_labels(self):
        pt = self.get_transformed_current_point(QgsCoordinateReferenceSystem("EPSG:4326"))
        self.layout.itemById(self.page_label_id).setText(str(self.current_page))
        self.layout.itemById(self.coords_label_id).setText('%.6f, %.6f'% (pt.x(), pt.y()))
        
    def iter_ordered_features(self, layers):
        #turn off all layer features
        for layer in layers:
            layer.setSubsetString('{}=-1'.format(self.id_field))
        for layer in layers:
            #turn on feature in beginning to init features
            layer.setSubsetString('')
            layer_ids = [f[self.id_field] for f in layer.getFeatures()]
            for i,feature in enumerate(layer.getFeatures()):
                # change current feature
                layer.setSubsetString('{}={}'.format(self.id_field, layer_ids[i]))
                yield layer, feature
            layer.setSubsetString('{}=-1'.format(self.id_field))
        #turn on all layer features back
        for layer in layers:
            layer.setSubsetString('')
                     
    def get_transformed_current_point(self, target_crs):
        geometry = self.current_feature.geometry()
        geometry = xform_geometry(geometry, self.current_layer.sourceCrs(), target_crs)
        return geometry.asPoint()
        
    def generate_table(self):
        table_item = self.layout.itemById(self.table_id).multiFrame()
        feature_fields = [i.name() for i in self.current_feature.fields()]
        feature_attributes = self.current_feature.attributes()
        trs = []
        for k,v in zip(feature_fields, feature_attributes):
            if k not in self.nonprint_columns:
                trs.append(f'<tr><th>{k}</th><td>{v}</td></tr>')
        html_table = f'<table>{"".join(trs)}</table>'
        table_item.setHtml(html_table)
        table_item.loadHtml()
        
    def update_layout(self):
        self.layout.refresh()
        self.recenter_main_map()
        self.extent_general_map()
        self.change_picture()
        self.generate_table()
        self.update_labels()
                

    def main(self):
        folder = self.generate_export_folder()    
        self.current_page = 1    
        for layer, feature in self.iter_ordered_features(layers):
            self.current_feature = feature
            self.current_layer = layer
            self.update_layout()
            self.export(folder)
            self.current_page += 1
    
    
x = PageGeneratorFramework()
x.current_layer = iface.activeLayer()
x.current_feature = next(x.current_layer.getFeatures())
x.update_layout()
#x.main()

