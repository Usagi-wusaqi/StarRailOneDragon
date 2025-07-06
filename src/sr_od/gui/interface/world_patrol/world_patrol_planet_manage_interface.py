import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidgetItem
from qfluentwidgets import PushButton, SettingCardGroup, TableWidget, InfoBarIcon

from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from one_dragon_qt.widgets.row import Row
from one_dragon_qt.widgets.vertical_scroll_interface import VerticalScrollInterface
from sr_od.context.sr_context import SrContext
from sr_od.sr_map.mys import mys_map_request_utils
from sr_od.sr_map.sr_map_def import Planet


class WorldPatrolPlanetManageInterface(VerticalScrollInterface):

    def __init__(self, ctx: SrContext, parent=None):
        self.ctx: SrContext = ctx

        VerticalScrollInterface.__init__(
            self,
            object_name='world_patrol_planet_manage_interface',
            content_widget=None, parent=parent,
            nav_text_cn='星球管理'
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

        # 第一行：管理模式、星球筛选、区域筛选、操作按钮
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
        data_group = SettingCardGroup('数据列表')
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
        headers = ['编号', 'ID', '中文名']
        self.data_table.setColumnCount(len(headers))
        self.data_table.setHorizontalHeaderLabels(headers)

        # 设置列宽
        self.data_table.setColumnWidth(0, 80)   # 编号
        self.data_table.setColumnWidth(1, 150)  # ID
        self.data_table.setColumnWidth(2, 200)  # 中文名

    def on_interface_shown(self):
        """
        画面加载时的初始化
        :return:
        """
        VerticalScrollInterface.on_interface_shown(self)
        self.on_refresh_clicked()

    def update_data_table(self) -> None:
        """更新数据表格"""
        self.data_table.setRowCount(0)

        # 星球管理模式 - 显示所有星球
        for planet in self.ctx.map_data.planet_list:
            self.add_planet_row(planet)

    def add_planet_row(self, planet: Planet) -> None:
        """添加星球行"""
        row = self.data_table.rowCount()
        self.data_table.insertRow(row)

        # 编号列（可编辑）
        num_item = QTableWidgetItem(str(planet.num))
        num_item.setFlags(num_item.flags() | Qt.ItemFlag.ItemIsEditable)
        self.data_table.setItem(row, 0, num_item)
        
        # ID列（可编辑）
        id_item = QTableWidgetItem(planet.id)
        id_item.setFlags(id_item.flags() | Qt.ItemFlag.ItemIsEditable)
        self.data_table.setItem(row, 1, id_item)
        
        # 中文名列（只读）
        cn_item = QTableWidgetItem(planet.cn)
        cn_item.setFlags(cn_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.data_table.setItem(row, 2, cn_item)

        # 存储原始星球对象引用（用于匹配变更）
        self.data_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, planet)
        # 存储原始中文名称（用于匹配变更）
        self.data_table.item(row, 0).setData(Qt.ItemDataRole.UserRole + 1, planet.cn)

    def on_sync_clicked(self) -> None:
        """从米游社同步星球数据"""
        # 禁用同步按钮，防止重复点击
        self.sync_btn.setEnabled(False)

        try:
            # 显示同步开始提示
            self.show_info_bar(title='同步完成', content='正在从米游社获取星球数据...', icon=InfoBarIcon.INFORMATION)

            # 获取米游社地图树
            mys_planet_list = mys_map_request_utils.get_planet_list()

            # 获取当前已有的星球
            existing_planets = set()
            for row in range(self.data_table.rowCount()):
                cn_item = self.data_table.item(row, 2)
                if cn_item:
                    existing_planets.add(cn_item.text())

            # 查找新的星球
            new_planets: list[Planet] = []
            for mys_planet in mys_planet_list:
                if mys_planet.cn not in existing_planets:
                    new_planets.append(mys_planet)

            if not new_planets:
                self.show_info_bar(title='同步完成', content='没有发现新的星球数据', icon=InfoBarIcon.SUCCESS)
                return

            # 获取当前最大编号
            max_num = 0
            for row in range(self.data_table.rowCount()):
                num_item = self.data_table.item(row, 0)
                if num_item:
                    try:
                        num = int(num_item.text())
                        max_num = max(max_num, num)
                    except ValueError:
                        continue

            # 添加新星球到表格
            added_count = 0
            for i, mys_planet in enumerate(new_planets):
                # 生成新的编号（当前最大编号+1+索引）
                new_num = max_num + 1 + i

                # 生成ID（从中文名生成简化ID）
                new_id = self.generate_planet_id(mys_planet.cn)

                # 检查ID是否已存在，如果存在则添加后缀
                existing_ids = set()
                for row in range(self.data_table.rowCount()):
                    id_item = self.data_table.item(row, 1)
                    if id_item:
                        existing_ids.add(id_item.text())

                original_id = new_id
                counter = 1
                while new_id in existing_ids:
                    new_id = f"{original_id}{counter}"
                    counter += 1

                # 创建新的Planet对象
                new_planet = Planet(new_num, new_id, mys_planet.cn)

                # 添加到表格
                self.add_planet_row(new_planet)
                added_count += 1

            self.show_info_bar(title='同步完成', content=f'成功添加了 {added_count} 个新星球', icon=InfoBarIcon.SUCCESS)

        except Exception as e:
            self.show_info_bar(title='同步失败', content=f'从米游社同步数据时发生错误: {str(e)}',icon=InfoBarIcon.ERROR)
            log.error('同步失败', exc_info=True)
        finally:
            # 重新启用同步按钮
            self.sync_btn.setEnabled(True)

    def generate_planet_id(self, planet_name: str) -> str:
        """
        根据星球名称生成ID
        Args:
            planet_name: 星球名称-中文

        Returns:
            星球ID
        """
        try:
            from pypinyin import pinyin, lazy_pinyin, Style
            chinese = re.sub(r'[^\u4e00-\u9fa5]', 'planet_name', planet_name)
            return ''.join(lazy_pinyin(chinese, style=Style.FIRST_LETTER)).upper()
        except Exception as e:
            log.error('无法导入pypinyin，无法生成星球ID')
            return 'AUTOGEN'

    def on_save_clicked(self) -> None:
        """保存修改"""
        try:
            new_planet_list: list[Planet] = []  # 存储星球变更信息

            for row in range(self.data_table.rowCount()):
                num_item = self.data_table.item(row, 0)
                id_item = self.data_table.item(row, 1)
                cn_item = self.data_table.item(row, 2)
                new_planet_list.append(Planet(
                    num=int(num_item.text()),
                    uid=id_item.text(),
                    cn=cn_item.text(),
                ))

            err_msg = self.validate_planet_data(new_planet_list)
            if err_msg is not None:
                self.show_info_bar(title='数据验证失败', content=err_msg, icon=InfoBarIcon.ERROR)
                return

            # 调用sr_map_data中的保存方法
            self.ctx.map_data.save_planet_data(new_planet_list)

            self.show_info_bar(title='保存成功', content=f'星球数据已成功保存', icon=InfoBarIcon.SUCCESS)
            self.on_refresh_clicked()
        except Exception as e:
            self.show_info_bar(title='保存失败', content=f'保存数据时发生错误: {str(e)}', icon=InfoBarIcon.ERROR)
            log.error('保存失败', exc_info=True)

    def validate_planet_data(self, planet_list: list[Planet]) -> str | None:
        """
        验证星球数据的有效性
        Args:
            planet_list:

        Returns:
            None: 通过验证
            str: 错误信息
        """
        # 检查编号是否重复
        nums = [p.num for p in planet_list]
        if len(nums) != len(set(nums)):
            return '星球编号不能重复'

        # 检查ID是否重复
        ids = [p.id for p in planet_list]
        if len(ids) != len(set(ids)):
            return '星球ID不能重复'

        # 检查中文名是否重复
        cns = [p.cn for p in planet_list]
        if len(cns) != len(set(cns)):
            return '星球中文名不能重复'

        # 检查必填字段
        for i, p in enumerate(planet_list):
            if not p.id.strip():
                return f'第{i+1}行的星球ID不能为空'

            if not p.cn.strip():
                return f'第{i+1}行的星球中文名不能为空'

        return None

    def on_refresh_clicked(self) -> None:
        """刷新数据"""
        self.ctx.map_data.load_map_data()
        self.setup_table_headers()
        self.update_data_table()
