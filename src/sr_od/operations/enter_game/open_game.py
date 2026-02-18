import os
import subprocess
import winreg

from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from one_dragon.utils.log_utils import log
from sr_od.context.sr_context import SrContext

# 星穹铁道会忽略 -screen-width/-screen-height/-screen-fullscreen 命令行参数
# 需要通过注册表设置分辨率和显示模式
_REGISTRY_SUBKEYS = {
    'cn': r'Software\miHoYo\崩坏：星穹铁道',
    'us': r'Software\Cognosphere\Star Rail',
    'eu': r'Software\Cognosphere\Star Rail',
    'asia': r'Software\Cognosphere\Star Rail',
    'twhkmo': r'Software\Cognosphere\Star Rail',
}

_REG_GRAPHICS_SETTINGS = 'GraphicsSettings_PCResolution_h431323223'
_REG_SCREEN_WIDTH = 'Screenmanager Resolution Width_h182942802'
_REG_SCREEN_HEIGHT = 'Screenmanager Resolution Height_h2627697771'
_REG_FULLSCREEN_MODE = 'Screenmanager Fullscreen mode_h3630240806'

_REG_VALUE_NAMES = (_REG_GRAPHICS_SETTINGS, _REG_SCREEN_WIDTH, _REG_SCREEN_HEIGHT, _REG_FULLSCREEN_MODE)

# 备份的注册表值，用于关闭游戏后恢复
_backup_subkey: str | None = None
_backup_values: dict[str, tuple[bytes | int, int]] | None = None


def restore_resolution_registry() -> None:
    """恢复注册表中的分辨率设置为打开游戏前的值"""
    global _backup_subkey, _backup_values
    if _backup_subkey is None or _backup_values is None:
        return

    subkey = _backup_subkey
    values = _backup_values
    _backup_subkey = None  # 只恢复一次
    _backup_values = None

    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, subkey, 0, winreg.KEY_WRITE) as key:
        for name, (value, reg_type) in values.items():
            winreg.SetValueEx(key, name, 0, reg_type, value)
    log.info('注册表分辨率设置已恢复')


class OpenGame(Operation):

    def __init__(self, ctx: SrContext):
        self.ctx: SrContext = ctx
        Operation.__init__(self, ctx, op_name=gt('打开游戏'),
                           need_check_game_win=False)

    def _set_resolution_registry(self, width: int, height: int, full_screen: str) -> None:
        """通过注册表设置游戏分辨率和显示模式
        星穹铁道游戏内设置会覆盖命令行的 -screen-width/-screen-height/-screen-fullscreen 参数，需要通过注册表来设置。
        """
        region = self.ctx.game_account_config.game_region
        subkey = _REGISTRY_SUBKEYS.get(region)
        if subkey is None:
            log.warning('不支持通过注册表设置分辨率的区服: %s，跳过', region)
            return

        # 显示模式转换: config '0'(窗口化) -> registry 3, config '1'(全屏) -> registry 1
        fullscreen_mode = 1 if full_screen == '1' else 3
        is_full_screen = fullscreen_mode == 1

        # 备份当前注册表值，用于关闭游戏后恢复；写入目标分辨率和显示模式
        global _backup_subkey, _backup_values
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, subkey, 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
            _, num_values, _ = winreg.QueryInfoKey(key)
            values: dict[str, tuple[bytes | int, int]] = {}
            for i in range(num_values):
                name, data, reg_type = winreg.EnumValue(key, i)
                if name in _REG_VALUE_NAMES:
                    values[name] = (data, reg_type)
            _backup_subkey = subkey if values else None
            _backup_values = values if values else None

            json_str = f'{{"width":{width},"height":{height},"isFullScreen":{str(is_full_screen).lower()}}}\0'
            winreg.SetValueEx(key, _REG_GRAPHICS_SETTINGS, 0, winreg.REG_BINARY, json_str.encode('ascii'))
            winreg.SetValueEx(key, _REG_SCREEN_WIDTH, 0, winreg.REG_DWORD, width)
            winreg.SetValueEx(key, _REG_SCREEN_HEIGHT, 0, winreg.REG_DWORD, height)
            winreg.SetValueEx(key, _REG_FULLSCREEN_MODE, 0, winreg.REG_DWORD, fullscreen_mode)

        log.info('注册表分辨率设置成功: %dx%d 显示模式=%s', width, height, '全屏' if is_full_screen else '窗口化')

    @operation_node(name='打开游戏', is_start_node=True)
    def open_game(self) -> OperationRoundResult:
        """
        打开游戏
        :return:
        """
        if self.ctx.game_account_config.game_path == '':
            return self.round_fail('未配置游戏路径')
        full_path = self.ctx.game_account_config.game_path
        log.info('尝试自动启动游戏 路径为 %s', full_path)
        # 获取文件夹路径
        dir_path = os.path.dirname(full_path)
        exe_name = os.path.basename(full_path)
        command = f'cmd /c "start "" "{dir_path}\{exe_name}"'
        if self.ctx.game_config.launch_argument:
            screen_size = self.ctx.game_config.screen_size
            screen_width = int(screen_size.split('x')[0])
            screen_height = int(screen_size.split('x')[1])
            full_screen = self.ctx.game_config.full_screen

            # 通过注册表设置分辨率和显示模式（命令行参数对星穹铁道无效）
            self._set_resolution_registry(screen_width, screen_height, full_screen)

            # 仅保留有效的命令行参数: -popupwindow 和 -monitor
            popup_window = "-popupwindow " if self.ctx.game_config.popup_window else ""
            monitor = self.ctx.game_config.monitor
            argument = f'{self.ctx.game_config.launch_argument_advance} {popup_window}-monitor {monitor}'
            command = f'{command} {argument}'
        command = f'{command} & exit"'
        log.info('命令行指令 %s', command)
        subprocess.Popen(command)
        return self.round_success(wait=5)
