from typing import Optional, List

from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon, SettingCardGroup

from one_dragon.base.config.config_item import ConfigItem
from one_dragon.base.operation.application_base import Application
from one_dragon.utils.log_utils import log
from one_dragon_qt.view.app_run_interface import AppRunInterface
from one_dragon_qt.widgets.column import Column
from one_dragon_qt.widgets.setting_card.combo_box_setting_card import ComboBoxSettingCard
from one_dragon_qt.widgets.setting_card.text_setting_card import TextSettingCard
from sr_od.app.large_map_recorder.large_map_recorder_app import LargeMapRecorder
from sr_od.context.sr_context import SrContext
from sr_od.sr_map.sr_map_def import Planet, Region


class LargeMapRecorderRunInterface(AppRunInterface):

    def __init__(self,
                 ctx: SrContext,
                 parent=None):
        self.ctx: SrContext = ctx
        self.app: Optional[LargeMapRecorder] = None

        AppRunInterface.__init__(
            self,
            ctx=ctx,
            object_name='sr_large_map_recorder_run_interface',
            nav_text_cn='大地图录制',
            parent=parent,
        )

        # 当前选择的星球和区域
        self.current_planet: Optional[Planet] = None
        self.current_region: Optional[Region] = None

    def get_widget_at_top(self) -> QWidget:
        content = Column()

        # 参数配置区域
        params_group = SettingCardGroup('参数配置')
        content.add_widget(params_group)

        # 星球选择
        self.planet_opt = ComboBoxSettingCard(
            icon=FluentIcon.GLOBE,
            title='星球选择',
            content='选择要录制的星球'
        )
        self.planet_opt.value_changed.connect(self.on_planet_changed)
        params_group.addSettingCard(self.planet_opt)

        # 区域选择
        self.region_opt = ComboBoxSettingCard(
            icon=FluentIcon.INFO,
            title='区域选择',
            content='选择要录制的区域'
        )
        self.region_opt.value_changed.connect(self.on_region_changed)
        params_group.addSettingCard(self.region_opt)

        self.run_mode_opt = ComboBoxSettingCard(
            icon=FluentIcon.PLAY,
            title='运行模式',
            content='选择录制模式'
        )
        params_group.addSettingCard(self.run_mode_opt)

        # 楼层列表
        self.floor_list_opt = TextSettingCard(
            icon=FluentIcon.INFO,
            title='指定楼层',
            content='要录制的楼层，用逗号分隔，如：-1,0,1',
            input_placeholder='例如：-1,0,1'
        )
        params_group.addSettingCard(self.floor_list_opt)

        # 行列表
        self.row_list_opt = TextSettingCard(
            icon=FluentIcon.INFO,
            title='指定行',
            content='要录制的行，用逗号分隔，如：1,2,3',
            input_placeholder='例如：1,2,3'
        )
        params_group.addSettingCard(self.row_list_opt)

        # 列列表
        self.col_list_opt = TextSettingCard(
            icon=FluentIcon.INFO,
            title='指定列',
            content='要录制的列，用逗号分隔，如：1,2,3',
            input_placeholder='例如：1,2,3'
        )
        params_group.addSettingCard(self.col_list_opt)

        return content

    def on_interface_shown(self):
        """
        界面显示时的初始化
        """
        AppRunInterface.on_interface_shown(self)
        self.init_planet_options()
        self.init_run_mode_options()

    def init_planet_options(self):
        """初始化星球选择选项"""
        try:
            # 创建星球选项列表
            planet_options = []
            for planet in self.ctx.map_data.planet_list:
                planet_options.append(ConfigItem(planet.cn, planet))

            # 设置选项
            self.planet_opt.set_options_by_list(planet_options)

            # 默认选择第一个星球
            if self.ctx.map_data.planet_list:
                self.current_planet = self.ctx.map_data.planet_list[0]
                self.planet_opt.setValue(self.current_planet, emit_signal=False)
                self.update_region_options()
        except Exception as e:
            log.error(f'初始化星球选项失败: {e}', exc_info=True)

    def init_run_mode_options(self):
        """初始化运行模式选项"""
        run_mode_options = [
            ConfigItem('完整录制', 'all'),
            ConfigItem('仅截图', 'screenshot'),
            ConfigItem('仅合并', 'merge'),
            ConfigItem('仅调整大小', 'adjust_size'),
            ConfigItem('仅保存', 'save')
        ]

        # 设置选项
        self.run_mode_opt.set_options_by_list(run_mode_options)

        # 默认选择完整录制
        self.run_mode_opt.setValue('all', emit_signal=False)

    def on_planet_changed(self, index: int, planet: Planet):
        """星球选择变化"""
        self.current_planet = planet
        self.update_region_options()

    def update_region_options(self):
        """更新区域选择选项"""
        if self.current_planet is None:
            return

        try:
            # 获取当前星球的区域列表
            region_list = self.ctx.map_data.get_region_list_by_planet(self.current_planet)

            # 按楼层分组显示区域
            region_map = {}
            for region in region_list:
                if region.cn not in region_map:
                    region_map[region.cn] = []
                region_map[region.cn].append(region)

            # 创建区域选项列表
            region_options = []
            for region_name, regions in region_map.items():
                if len(regions) == 1:
                    # 只有一个楼层的区域
                    region = regions[0]
                    display_name = region.cn
                    if region.floor != 0:
                        display_name += f' (F{region.floor})'
                    region_options.append(ConfigItem(display_name, region))
                else:
                    # 多个楼层的区域，选择主楼层（通常是0层）
                    main_region = None
                    for region in regions:
                        if region.floor == 0:
                            main_region = region
                            break
                    if main_region is None:
                        main_region = regions[0]

                    region_options.append(ConfigItem(main_region.cn, main_region))

            # 设置选项
            self.region_opt.set_options_by_list(region_options)

            # 默认选择第一个区域
            if region_list:
                self.current_region = region_list[0]
                self.region_opt.setValue(self.current_region, emit_signal=False)

        except Exception as e:
            log.error(f'更新区域选项失败: {e}', exc_info=True)

    def on_region_changed(self, index: int, region: Region):
        """区域选择变化"""
        self.current_region = region

    def parse_int_list(self, text: str) -> Optional[List[int]]:
        """
        解析整数列表字符串
        
        Args:
            text: 输入文本，如 "1,2,3"
            
        Returns:
            整数列表，解析失败返回None
        """
        if not text or not text.strip():
            return None
            
        try:
            return [int(x.strip()) for x in text.split(',') if x.strip()]
        except ValueError:
            return None

    def get_app(self) -> Application:
        """获取要运行的应用"""
        if self.current_region is None:
            log.error('请先选择要录制的区域')
            return None
            
        try:
            # 获取参数
            floor_list = self.parse_int_list(self.floor_list_opt.line_edit.text())
            row_list = self.parse_int_list(self.row_list_opt.line_edit.text())
            col_list = self.parse_int_list(self.col_list_opt.line_edit.text())
            
            # 创建应用实例
            app = LargeMapRecorder(
                ctx=self.ctx,
                region=self.current_region,
                floor_list_to_record=floor_list,
                row_list_to_record=row_list,
                col_list_to_record=col_list
            )
            
            return app
            
        except Exception as e:
            log.error(f'创建大地图录制应用失败: {e}', exc_info=True)
            return None
