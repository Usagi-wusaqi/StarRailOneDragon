import random
from typing import List, Optional, Tuple

import cv2
import numpy as np
from cv2.typing import MatLike

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.matcher.match_result import MatchResult, MatchResultList
from one_dragon.base.screen.template_info import TemplateInfo
from one_dragon.utils import cv2_utils
from one_dragon.utils.log_utils import log
from sr_od.config import game_const
from sr_od.context.sr_context import SrContext
from sr_od.sr_map.large_map_info import LargeMapInfo
from sr_od.sr_map.sr_map_def import Planet, Region

CUT_MAP_RECT = Rect(285, 190, 1300, 930)  # 主区域 在屏幕上截取大地图的区域
SUB_CUT_MAP_RECT = Rect(200, 190, 1600, 955)  # 子区域 在屏幕上截取大地图的区域
EMPTY_MAP_POS = Point(1350, 800)  # 地图空白区域 用于取消选择传送点 和 拖动地图
REGION_LIST_RECT = Rect(1480, 200, 1820, 1000)
FLOOR_LIST_PART = Rect(30, 580, 110, 1000)  # 外层地图和子地图的x轴不太一样 取一个并集

LARGE_MAP_POWER_RECT = Rect(1635, 54, 1678, 72)  # 大地图上显示体力的位置
EMPTY_COLOR: int = 210  # 大地图空白地方的颜色


def get_screen_map_rect(region: Region) -> Rect:
    """
    获取区域对应的屏幕上大地图范围
    :param region: 区域
    :return:
    """
    return CUT_MAP_RECT if region is None or region.parent is None else SUB_CUT_MAP_RECT


def get_screen_map_part(screen: MatLike, region: Region | None = None) -> MatLike:
    """
    获取截图中的大地图部分

    Args:
        screen: 游戏画面
        region: 区域

    Returns:
        MatLike: 大地图部分
    """
    screen_map_rect = get_screen_map_rect(region)
    return cv2_utils.crop_image_only(screen, screen_map_rect)


def get_planet(ctx: SrContext, screen: MatLike) -> Optional[Planet]:
    """
    从屏幕左上方 获取当前星球的名字
    :param ctx: 上下文
    :param screen: 游戏画面
    :return: 星球名称
    """
    area = ctx.screen_loader.get_area('大地图', '星球名称')
    planet_name_part = cv2_utils.crop_image_only(screen, area.rect)
    # cv2_utils.show_image(white_part, win_name='white_part')
    planet_name_str: str = ctx.ocr.run_ocr_single_line(planet_name_part)

    return ctx.map_data.best_match_planet_by_name(planet_name_str)


def get_active_region_name(ctx: SrContext, screen: MatLike) -> Optional[str]:
    """
    在大地图界面 获取右边列表当前选择的区域 白色字体
    :param ctx: 上下文
    :param screen: 大地图界面截图
    :return: 当前选择区域
    """
    lower = 230
    upper = 255
    part, _ = cv2_utils.crop_image(screen, REGION_LIST_RECT)
    bw = cv2.inRange(part, (lower, lower, lower), (upper, upper, upper))
    bw = cv2_utils.connection_erase(bw)
    # cv2_utils.show_image(bw, win_name='get_active_region_name_bw')
    left, right, top, bottom = cv2_utils.get_four_corner(bw)
    if left is None:
        return None
    rect = Rect(left[0] - 10, top[1] - 10, right[0] + 10, bottom[1] + 10)
    to_ocr: MatLike = cv2_utils.crop_image_only(part, rect)
    # cv2_utils.show_image(to_ocr, win_name='get_active_region_name', wait=0)
    return ctx.ocr.run_ocr_single_line(to_ocr, strict_one_line=False)


def get_active_floor(ctx: SrContext, screen: MatLike) -> Optional[str]:
    """
    在大地图界面 获取左下方当前选择的层数 黑色字体
    :param ctx: 上下文
    :param screen: 大地图界面截图
    :return: 当前选择区域
    """
    lower = 0
    upper = 90
    part, _ = cv2_utils.crop_image(screen, FLOOR_LIST_PART)
    bw = cv2.inRange(part, (lower, lower, lower), (upper, upper, upper))
    left, right, top, bottom = cv2_utils.get_four_corner(bw)
    if left is None:
        return None
    rect = Rect(left[0] - 10, top[1] - 10, right[0] + 10, bottom[1] + 10)
    to_ocr: MatLike = cv2_utils.crop_image_only(part, rect)
    # cv2_utils.show_image(to_ocr, win_name='get_active_floor', wait=0)

    return ctx.ocr.run_ocr_single_line(to_ocr)



def get_large_map_road_mask(map_image: MatLike,
                            sp_mask: MatLike = None) -> MatLike:
    """
    在地图中 按接近道路的颜色圈出地图的主体部分 过滤掉无关紧要的背景
    :param map_image: 地图图片
    :param sp_mask: 特殊点的掩码 道路掩码应该排除这部分
    :return: 道路掩码图 能走的部分是白色255
    """
    # 按道路颜色圈出 当前层的颜色
    l1 = 45
    u1 = 100
    lower_color = np.array([l1, l1, l1], dtype=np.uint8)
    upper_color = np.array([u1, u1, u1], dtype=np.uint8)
    road_mask_1 = cv2.inRange(map_image, lower_color, upper_color)
    # 按道路颜色圈出 其他层的颜色
    l2 = 120
    u2 = 150
    lower_color = np.array([l2, l2, l2], dtype=np.uint8)
    upper_color = np.array([u2, u2, u2], dtype=np.uint8)
    road_mask_2 = cv2.inRange(map_image, lower_color, upper_color)

    road_mask = cv2.bitwise_or(road_mask_1, road_mask_2)

    # 合并特殊点进行连通性检测
    to_check_connection = cv2.bitwise_or(road_mask, sp_mask) if sp_mask is not None else road_mask

    # 非道路连通块 < 50的(小的黑色块) 认为是噪点 加入道路
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(cv2.bitwise_not(to_check_connection), connectivity=4)
    large_components = []
    for label in range(1, num_labels):
        if stats[label, cv2.CC_STAT_AREA] < 50:
            large_components.append(label)
    for label in large_components:
        to_check_connection[labels == label] = 255

    # 找到多于500个像素点的连通道路(大的白色块) 这些才是真的路
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(to_check_connection, connectivity=4)
    large_components = []
    for label in range(1, num_labels):
        if stats[label, cv2.CC_STAT_AREA] > 500:
            large_components.append(label)
    real_road_mask = np.zeros(map_image.shape[:2], dtype=np.uint8)
    for label in large_components:
        real_road_mask[labels == label] = 255

    # 排除掉特殊点
    if sp_mask is not None:
        real_road_mask = cv2.bitwise_and(real_road_mask, cv2.bitwise_not(sp_mask))

    return real_road_mask


def get_large_map_rect_by_pos(lm_shape, mm_shape, possible_pos: tuple = None) -> Optional[Rect]:
    """
    :param lm_shape: 大地图尺寸
    :param mm_shape: 小地图尺寸
    :param possible_pos: 可能在大地图的位置 (x,y,d)。 (x,y) 是上次在的位置 d是移动的距离
    :return:
    """
    if possible_pos is not None:  # 传入了潜在位置 那就截取部分大地图再进行匹配
        mr = mm_shape[0] // 2  # 小地图半径
        x, y = int(possible_pos[0]), int(possible_pos[1])
        # 还没有移动的话 通常是第一个点 这时候先默认移动1秒距离判断
        r = 20 if len(possible_pos) < 3 or possible_pos[2] == 0 else int(possible_pos[2])
        ur = r + mr + 5  # 潜在位置半径 = 移动距离 + 小地图半径 + 5(多留一些边缘匹配)
        lm_offset_x = x - ur
        lm_offset_y = y - ur
        lm_offset_x2 = x + ur
        lm_offset_y2 = y + ur
        if lm_offset_x < 0:  # 防止越界
            lm_offset_x = 0
        if lm_offset_y < 0:
            lm_offset_y = 0
        if lm_offset_x2 > lm_shape[1]:
            lm_offset_x2 = lm_shape[1]
        if lm_offset_y2 > lm_shape[0]:
            lm_offset_y2 = lm_shape[0]
        return Rect(lm_offset_x, lm_offset_y, lm_offset_x2, lm_offset_y2)
    else:
        return None



def match_screen_in_large_map(ctx: SrContext, screen: MatLike, region: Region) -> Tuple[MatLike, MatchResult]:
    """
    在当前屏幕截图中扣出大地图部分，并匹配到完整大地图上获取偏移量
    :param ctx:
    :param screen: 游戏屏幕截图
    :param region: 目标区域
    :return:
    """
    screen_map_rect = get_screen_map_rect(region)
    screen_part = cv2_utils.crop_image_only(screen, screen_map_rect)
    lm_info = ctx.map_data.get_large_map_info(region)
    result: MatchResultList = cv2_utils.match_template(lm_info.raw, screen_part, 0.7)

    return screen_part, result.max


def drag_in_large_map(ctx: SrContext, dx: Optional[int] = None, dy: Optional[int] = None):
    """
    在大地图上拖动
    :param ctx:
    :param dx:
    :param dy:
    :return:
    """
    if dx is None:
        dx = 1 if random.randint(0, 1) == 1 else -1
    if dy is None:
        dy = 1 if random.randint(0, 1) == 1 else -1
    fx, fy = EMPTY_MAP_POS.tuple()
    drag_distance = -200
    tx, ty = fx + drag_distance * dx, fy + drag_distance * dy
    log.info('拖动地图 %s -> %s', (fx, fy), (tx, ty))
    ctx.controller.drag_to(end=Point(tx, ty), start=Point(fx, fy), duration=1)


def get_map_next_drag(lm_pos: Point, offset: MatchResult) -> Tuple[int, int]:
    """
    判断当前显示的部分大地图是否已经涵盖到目标点的坐标
    如果没有 则返回需要往哪个方向拖动
    :param lm_pos: 目标点在大地图上的坐标
    :param offset: 偏移量
    :return: 后续拖动方向 正代表坐标需要增加 正代表坐标需要减少
    """
    # 匹配结果矩形
    x1, y1 = offset.x, offset.y
    x2, y2 = x1 + offset.w, y1 + offset.h
    # 目标点坐标
    x, y = lm_pos.x, lm_pos.y

    dx, dy = 0, 0
    if x > x2:
        dx = 1
    elif x < x1:
        dx = -1
    if y > y2:
        dy = 1
    elif y < y1:
        dy = -1
    return dx, dy
