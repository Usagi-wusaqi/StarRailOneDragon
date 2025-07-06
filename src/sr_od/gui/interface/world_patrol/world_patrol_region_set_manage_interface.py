import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidgetItem
from qfluentwidgets import PushButton, SettingCardGroup, TableWidget, InfoBarIcon, ComboBox

from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon_qt.widgets.row import Row
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from sr_od.context.sr_context import SrContext
from sr_od.sr_map.mys import mys_map_request_utils
from sr_od.sr_map.sr_map_def import Planet, RegionSet


class WorldPatrolRegionSetManageInterface(VerticalScrollInterface):

    def __init__(self, ctx: SrContext, parent=None):
        self.ctx: SrContext = ctx
        self.current_planet: Planet | None = None

        VerticalScrollInterface.__init__(
            self,
            object_name='world_patrol_region_set_manage_interface',
            content_widget=None, parent=parent,
            nav_text_cn='区域管理'
        )

    def get_content_widget(self) -> QWidget:
        """
        子界面内的内容组件 由子类实现
        :return:
        """
        content_widget = QWidget()
        # 创建 QVBoxLayout 作为主布局（上下布局）
        main_layout = QVBoxLayout(content_widget)

        # 添加控制面板
        main_layout.addLayout(self.get_control_layout())
        main_layout.addSpacing(10)
        
        # 添加数据表格
        main_layout.addLayout(self.get_table_layout(), stretch=1)

        return content_widget

    def get_control_layout(self) -> QVBoxLayout:
        layout = QVBoxLayout()

        # 控制面板
        control_group = SettingCardGroup('控制面板')
        layout.addWidget(control_group)

        # 第一行：星球选择
        planet_row = Row()
        
        # 星球选择下拉框
        self.planet_combo = ComboBox()
        self.planet_combo.setPlaceholderText('选择星球')
        self.planet_combo.currentTextChanged.connect(self.on_planet_changed)
        planet_row.add_widget(self.planet_combo, stretch=0)
        
        planet_row.add_stretch(1)
        layout.addWidget(planet_row)

        # 第二行：操作按钮
        control_row = Row()
        
        # 操作按钮
        self.refresh_btn = PushButton(text=gt('刷新数据'))
        self.refresh_btn.clicked.connect(self.on_refresh_clicked)
        control_row.add_widget(self.refresh_btn)

        self.sync_btn = PushButton(text=gt('从米游社同步'))
        self.sync_btn.clicked.connect(self.on_sync_clicked)
        control_row.add_widget(self.sync_btn)

        self.save_btn = PushButton(text=gt('保存修改'))
        self.save_btn.clicked.connect(self.on_save_clicked)
        control_row.add_widget(self.save_btn)

        control_row.add_stretch(1)
        layout.addWidget(control_row)

        return layout

    def get_table_layout(self) -> QVBoxLayout:
        layout = QVBoxLayout()

        # 数据显示区域
        data_group = SettingCardGroup('区域列表')
        layout.addWidget(data_group)

        # 创建表格
        self.data_table = TableWidget()
        self.data_table.setMinimumHeight(500)
        self.data_table.setBorderVisible(True)
        self.data_table.setBorderRadius(8)
        self.data_table.setWordWrap(True)
        self.data_table.verticalHeader().hide()
        self.data_table.setSelectionBehavior(TableWidget.SelectionBehavior.SelectRows)

        # 设置表格列
        self.setup_table_headers()

        layout.addWidget(self.data_table)

        return layout

    def setup_table_headers(self):
        """设置表格标题"""
        headers = ['编号', 'ID', '中文名', '楼层', '父区域名称', '父区域楼层', '入口模板ID', '入口坐标']
        self.data_table.setColumnCount(len(headers))
        self.data_table.setHorizontalHeaderLabels(headers)

        # 设置列宽
        self.data_table.setColumnWidth(0, 80)   # 编号
        self.data_table.setColumnWidth(1, 120)  # ID
        self.data_table.setColumnWidth(2, 150)  # 中文名
        self.data_table.setColumnWidth(3, 100)  # 楼层
        self.data_table.setColumnWidth(4, 120)  # 父区域名称
        self.data_table.setColumnWidth(5, 100)  # 父区域楼层
        self.data_table.setColumnWidth(6, 120)  # 入口模板ID
        self.data_table.setColumnWidth(7, 120)  # 入口坐标

    def on_interface_shown(self):
        """
        画面加载时的初始化
        :return:
        """
        VerticalScrollInterface.on_interface_shown(self)
        self.init_planet_combo()
        self.on_refresh_clicked()

    def init_planet_combo(self):
        """初始化星球下拉框"""
        self.planet_combo.clear()
        for planet in self.ctx.map_data.planet_list:
            self.planet_combo.addItem(planet.cn)
        
        # 默认选择第一个星球
        if self.ctx.map_data.planet_list:
            self.current_planet = self.ctx.map_data.planet_list[0]
            self.planet_combo.setCurrentIndex(0)

    def on_planet_changed(self, planet_name: str):
        """星球选择变化"""
        for planet in self.ctx.map_data.planet_list:
            if planet.cn == planet_name:
                self.current_planet = planet
                self.update_data_table()
                break

    def update_data_table(self) -> None:
        """更新数据表格"""
        self.data_table.setRowCount(0)

        if self.current_planet is None:
            return

        # 获取当前星球的区域集合列表
        region_set_list = self.ctx.map_data.get_region_set_by_planet(self.current_planet)
        self.set_region_set_list(region_set_list)

    def set_region_set_list(self, region_set_list: list[RegionSet]) -> None:
        """
        设置全部区域到表格上

        Args:
            region_set_list: 区域列表

        Returns:
            None
        """
        self.data_table.setRowCount(0)
        for region_set in region_set_list:
            self.add_region_set_row(region_set)

    def add_region_set_row(self, region_set: RegionSet) -> None:
        """添加区域集合行"""
        row = self.data_table.rowCount()
        self.data_table.insertRow(row)

        # 编号列（可编辑）
        num_item = QTableWidgetItem(str(region_set.num))
        num_item.setFlags(num_item.flags() | Qt.ItemFlag.ItemIsEditable)
        self.data_table.setItem(row, 0, num_item)
        
        # ID列（可编辑）
        id_item = QTableWidgetItem(region_set.id)
        id_item.setFlags(id_item.flags() | Qt.ItemFlag.ItemIsEditable)
        self.data_table.setItem(row, 1, id_item)
        
        # 中文名列（只读）
        cn_item = QTableWidgetItem(region_set.cn)
        cn_item.setFlags(cn_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.data_table.setItem(row, 2, cn_item)
        
        # 楼层列（可编辑）
        floors_str = ','.join(map(str, region_set.floors)) if region_set.floors else '0'
        floors_item = QTableWidgetItem(floors_str)
        floors_item.setFlags(floors_item.flags() | Qt.ItemFlag.ItemIsEditable)
        self.data_table.setItem(row, 3, floors_item)
        
        # 父区域名称列（可编辑）
        parent_name_item = QTableWidgetItem(region_set.parent_region_name or '')
        parent_name_item.setFlags(parent_name_item.flags() | Qt.ItemFlag.ItemIsEditable)
        self.data_table.setItem(row, 4, parent_name_item)
        
        # 父区域楼层列（可编辑）
        parent_floor_item = QTableWidgetItem(str(region_set.parent_region_floor) if region_set.parent_region_floor is not None else '')
        parent_floor_item.setFlags(parent_floor_item.flags() | Qt.ItemFlag.ItemIsEditable)
        self.data_table.setItem(row, 5, parent_floor_item)
        
        # 入口模板ID列（可编辑）
        template_id_item = QTableWidgetItem(region_set.enter_template_id or '')
        template_id_item.setFlags(template_id_item.flags() | Qt.ItemFlag.ItemIsEditable)
        self.data_table.setItem(row, 6, template_id_item)
        
        # 入口坐标列（可编辑）
        lm_pos_str = ','.join(map(str, region_set.enter_lm_pos)) if region_set.enter_lm_pos else ''
        lm_pos_item = QTableWidgetItem(lm_pos_str)
        lm_pos_item.setFlags(lm_pos_item.flags() | Qt.ItemFlag.ItemIsEditable)
        self.data_table.setItem(row, 7, lm_pos_item)

        # 存储原始区域集合对象引用（用于匹配变更）
        self.data_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, region_set)
        # 存储原始中文名称（用于匹配变更）
        self.data_table.item(row, 0).setData(Qt.ItemDataRole.UserRole + 1, region_set.cn)

    def on_sync_clicked(self) -> None:
        """从米游社同步区域数据"""
        if self.current_planet is None:
            self.show_info_bar(title='同步失败', content='请先选择星球', icon=InfoBarIcon.ERROR)
            return

        # 禁用同步按钮，防止重复点击
        self.sync_btn.setEnabled(False)

        try:
            # 显示同步开始提示
            self.show_info_bar(title='同步开始', content='正在从米游社获取区域数据...', icon=InfoBarIcon.INFORMATION)

            # 获取米游社区域列表
            mys_region_set_list: list[RegionSet] = mys_map_request_utils.get_region_set_list(self.current_planet.cn)

            # 获取当前已有的区域
            table_region_set_list: list[RegionSet] = self.get_region_set_list_from_table()
            table_region_name_map: dict[str, RegionSet] = {region_set.cn: region_set for region_set in table_region_set_list}
            table_region_id_map: dict[str, RegionSet] = {region_set.id: region_set for region_set in table_region_set_list}

            # 按米游社接口返回的顺序排列区域
            whole_region_set_list: list[RegionSet] = []
            new_region_set_list: list[RegionSet] = []
            for mys_region_set in mys_region_set_list:
                if mys_region_set.cn in table_region_name_map:
                    whole_region_set_list.append(table_region_name_map[mys_region_set.cn])
                else:
                    new_region_set_list.append(mys_region_set)
                    whole_region_set_list.append(mys_region_set)

            if len(new_region_set_list) == 0:
                self.show_info_bar(title='同步完成', content='没有发现新的区域数据', icon=InfoBarIcon.SUCCESS)
                return

            # 获取当前最大编号
            max_num = 0
            for table_region_set in table_region_set_list:
                if table_region_set.num > max_num:
                    max_num = table_region_set.num

            # 给新区域设置新的编号和ID
            for i, new_region_set in enumerate(new_region_set_list):
                # 生成新的编号（当前最大编号+1+索引）
                new_region_set.num = max_num + 1 + i

                # 生成ID（从中文名生成简化ID）
                new_id = self.generate_region_id(new_region_set.cn)
                id_prefix = new_id

                id_idx: int = 0
                while new_id in table_region_id_map:
                    id_idx += 1
                    new_id = f'{id_prefix}{id_idx}'
                new_region_set.id = new_id

            # 刷新表格显示
            self.set_region_set_list(whole_region_set_list)
            self.show_info_bar(title='同步完成', content=f'成功添加了 {len(new_region_set_list)} 个新区域', icon=InfoBarIcon.SUCCESS)
        except Exception as e:
            self.show_info_bar(title='同步失败', content=f'从米游社同步数据时发生错误: {str(e)}', icon=InfoBarIcon.ERROR)
            log.error('同步失败', exc_info=True)
        finally:
            # 重新启用同步按钮
            self.sync_btn.setEnabled(True)

    def generate_region_id(self, region_name: str) -> str:
        """
        根据区域名称生成ID
        Args:
            region_name: 区域名称-中文

        Returns:
            区域ID
        """
        try:
            from pypinyin import pinyin, lazy_pinyin, Style
            chinese = re.sub(r'[^\u4e00-\u9fa5]', '', region_name)
            return ''.join(lazy_pinyin(chinese, style=Style.FIRST_LETTER)).upper()
        except Exception as e:
            log.error('无法导入pypinyin，无法生成区域ID')
            return 'AUTOGEN'

    def get_region_set_list_from_table(self) -> list[RegionSet]:
        """
        获取表格中的区域列表
        Returns:
            list[RegionSet]: 区域列表
        """
        region_set_list: list[RegionSet] = []  # 存储区域集合变更信息

        for row in range(self.data_table.rowCount()):
            num_item = self.data_table.item(row, 0)
            id_item = self.data_table.item(row, 1)
            cn_item = self.data_table.item(row, 2)
            floors_item = self.data_table.item(row, 3)
            parent_name_item = self.data_table.item(row, 4)
            parent_floor_item = self.data_table.item(row, 5)
            template_id_item = self.data_table.item(row, 6)
            lm_pos_item = self.data_table.item(row, 7)

            # 解析楼层列表
            floors_str = floors_item.text().strip()
            if floors_str:
                try:
                    floors = [int(f.strip()) for f in floors_str.split(',') if f.strip()]
                except ValueError:
                    floors = [0]
            else:
                floors = [0]

            # 解析父区域楼层
            parent_floor_str = parent_floor_item.text().strip()
            parent_floor = int(parent_floor_str) if parent_floor_str else None

            # 解析入口坐标
            lm_pos_str = lm_pos_item.text().strip()
            if lm_pos_str:
                try:
                    lm_pos = [int(p.strip()) for p in lm_pos_str.split(',') if p.strip()]
                    if len(lm_pos) != 2:
                        lm_pos = None
                except ValueError:
                    lm_pos = None
            else:
                lm_pos = None

            region_set = RegionSet(
                num=int(num_item.text()),
                uid=id_item.text(),
                cn=cn_item.text(),
                floors=floors,
                parent_region_name=parent_name_item.text().strip() or None,
                parent_region_floor=parent_floor,
                enter_template_id=template_id_item.text().strip() or None,
                enter_lm_pos=lm_pos,
            )
            region_set_list.append(region_set)

        return region_set_list

    def on_save_clicked(self) -> None:
        """保存修改"""
        if self.current_planet is None:
            self.show_info_bar(title='保存失败', content='请先选择星球', icon=InfoBarIcon.ERROR)
            return

        try:
            new_region_set_list = self.get_region_set_list_from_table()
            err_msg = self.validate_region_set_data(new_region_set_list)
            if err_msg is not None:
                self.show_info_bar(title='数据验证失败', content=err_msg, icon=InfoBarIcon.ERROR)
                return

            # 调用sr_map_data中的保存方法
            self.ctx.map_data.save_region_set_data(self.current_planet, new_region_set_list)

            self.show_info_bar(title='保存成功', content=f'区域数据已成功保存', icon=InfoBarIcon.SUCCESS)
            self.on_refresh_clicked()
        except Exception as e:
            self.show_info_bar(title='保存失败', content=f'保存数据时发生错误: {str(e)}', icon=InfoBarIcon.ERROR)
            log.error('保存失败', exc_info=True)

    def validate_region_set_data(self, region_set_list: list[RegionSet]) -> str | None:
        """
        验证区域集合数据的有效性
        Args:
            region_set_list:

        Returns:
            None: 通过验证
            str: 错误信息
        """
        # 检查编号是否重复
        nums = [rs.num for rs in region_set_list]
        if len(nums) != len(set(nums)):
            return '区域编号不能重复'

        # 检查ID是否重复
        ids = [rs.id for rs in region_set_list]
        if len(ids) != len(set(ids)):
            return '区域ID不能重复'

        # 检查中文名是否重复
        cns = [rs.cn for rs in region_set_list]
        if len(cns) != len(set(cns)):
            return '区域中文名不能重复'

        # 检查必填字段
        for i, rs in enumerate(region_set_list):
            if not rs.id.strip():
                return f'第{i+1}行的区域ID不能为空'

            if not rs.cn.strip():
                return f'第{i+1}行的区域中文名不能为空'

        return None

    def on_refresh_clicked(self) -> None:
        """刷新数据"""
        self.ctx.map_data.load_map_data()
        self.setup_table_headers()
        self.update_data_table()
