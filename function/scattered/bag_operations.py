"""背包操作集合：装备栏整理、空格识别及消耗品使用。"""

from dataclasses import dataclass
import time

import numpy as np


def equipment_row_tops(image):
    """由装备栏49像素格线定位完整行，支持滚动后顶部不足一行的画面。"""
    if image is None or image.ndim != 3 or image.shape[0] < 431 or image.shape[1] < 910:
        return ()
    starts = []
    for y in range(90, 429):
        filled = sum(np.all(image[y, x:x + 5, :3] == [61, 38, 20]) and
                     np.all(image[y + 1, x:x + 5, :3] == [74, 52, 27])
                     for x in (485, 534, 583, 632, 681, 730, 779, 828))
        empty = sum(np.all(image[y, x:x + 5, :3] == [65, 31, 0]) and
                    np.all(image[y + 1, x:x + 5, :3] == [99, 66, 26])
                    for x in (485, 534, 583, 632, 681, 730, 779, 828))
        if filled >= 2:
            starts.append(y)
        if empty >= 2:
            starts.append(y - 2)
    starts = sorted(set(starts))
    starts = [y for y in starts if y + 49 in starts or y - 49 in starts]
    if not starts:
        return ()
    phase = starts[0]
    while phase >= 137:
        phase -= 49
    return tuple(y for y in range(phase - 49, 431, 49) if y + 2 >= 88 and y + 45 <= 431)


def equipment_cell_empty(image, left, top, *, include_unopened=False):
    """核对完整23×23空图案；扫描可接受未开放尾格，使用耗尽核对只接受真空格。"""
    if image is None or image.ndim != 3 or top < 0 or left < 0:
        return False
    sample = image[top + 10:top + 33, left + 10:left + 33, :3]
    if sample.shape != (23, 23, 3):
        return False
    return bool(np.all(sample == [99, 66, 26]) or
                include_unopened and np.all(sample == [81, 44, 0]))


def equipment_page_has_empty(image):
    """整理后的页面是否含真实空格；必须在使用任何道具前读取，避免新空洞截断尾部。"""
    states = [equipment_cell_empty(image, 466 + column * 49, top, include_unopened=True)
              for top in equipment_row_tops(image) for column in range(9)]
    # 相邻页可能重合，重合部分已用完的旧空洞后若仍有道具，不能终止后续页。
    return bool(states and any(states) and all(states[states.index(True):]))


def find_bag_reward_close(image):
    """在单件、礼包两处范围识别普通或悬停红叉，返回范围与实际中心，未命中返回None。"""
    from function.common.bg_img_match import match_p_in_w
    from function.globals import g_resources

    # 范围按普通、悬停及关闭动画的实测位置收紧，保留数像素位移余量，不搜索整个弹窗。
    for rect in ([432, 178, 466, 208], [680, 188, 714, 218]):
        for name in ("退出.png", "退出_被选中.png"):
            status, position = match_p_in_w(source_img=image, source_range=rect,
                                           template=g_resources.RESOURCE_P["common"][name],
                                           match_tolerance=.95)
            if status == 0:
                raise RuntimeError("奖励窗识别失败；不继续使用消耗品")
            if status == 2:
                return tuple(rect), (position[0] + rect[0], position[1] + rect[1])
    return None


def close_bag_reward_windows(faa, control=None):
    """只点击识别到的奖励红叉，最多3秒核准奖励和使用菜单退出；失败时停止后续背包操作。"""
    from function.common.bg_img_match import match_p_in_w
    from function.common.bg_img_screenshot import capture_image_png
    from function.globals import g_resources
    from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER

    deadline = time.monotonic() + 3
    closed_windows = set()
    for _check_index in range(75):
        if control is not None:
            control.check()
        time.sleep(.04)
        if time.monotonic() >= deadline:
            break
        image = capture_image_png(handle=faa.handle, root_handle=faa.handle_360,
                                  raw_range=[0, 0, 950, 600])
        reward = find_bag_reward_close(image)
        if reward is not None:
            window, point = reward
            if window not in closed_windows:
                if control is not None:
                    control.check()
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=faa.handle, x=point[0], y=point[1])
                closed_windows.add(window)
            continue
        menu_visible = False
        for name in ("物品-背包-使用.png", "物品-背包-使用-被选中.png"):
            status, _point = match_p_in_w(source_img=image, source_range=[466, 86, 950, 500],
                                         template=g_resources.RESOURCE_P["item"][name], match_tolerance=.98)
            if status == 0:
                raise RuntimeError("使用菜单识别失败；不继续使用消耗品")
            menu_visible |= status == 2
        if not menu_visible:
            time.sleep(.02)
            return
    raise RuntimeError("奖励窗或使用菜单3秒内未关闭，不继续读取背包或使用物品")


def sort_equipment_inventory(faa, control=None):
    """沿用FAA整理坐标及等待，整理使位置记忆失效，随后必须重建库存再使用。"""
    from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER

    if control is not None:
        control.check()
    close_bag_reward_windows(faa, control)
    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=faa.handle, x=905, y=475)
    # 整理会重新排序全部装备，不能在队列入队后立刻按旧格位点击。
    time.sleep(2)
    if control is not None:
        control.check()


@dataclass(frozen=True)
class BagItem:
    """一个实际装备格；未知图标保留占用，不当作空格或数量0。"""
    name: str | None
    count: int | None
    bound: bool | None
    empty: bool = False


@dataclass(frozen=True)
class ConsumableReport:
    """库存回调模式的实测结果；submitted含失败提交，completed只计确认扣减。"""
    before: tuple
    after: tuple
    submitted: int
    completed: int | None = None
    blocked: bool = False


def _use_selected_bag_consumable(faa, targets, point, *, control=None, use_ready=None, previous_count=None):
    """选择一件已定位的消耗品，提交一次使用，并完成奖励窗口处理。

    Args:
        faa: 提供游戏窗口句柄的FAA对象。
        targets: 本次物品白名单，供完成判定和记账回调使用。
        point: 已识别的物品图标坐标。
        control: 可选中止对象；消费点击通过其锁提交。
        use_ready: 可选服务器奖励完成判定。
        previous_count: 使用前实测数量；普通物品等到奖励或扣减后才开始关闭窗口。

    Returns:
        int: 一次已提交的使用操作；不代表服务器实际产量。

    Raises:
        ValueError: 普通调用缺少使用前实测数量，未提交使用。
        RuntimeError: 使用按钮、奖励窗口或消耗核对失败，不重复提交该物品。
    """
    from function.common.bg_img_match import match_p_in_w
    from function.common.bg_img_screenshot import capture_image_png
    from function.globals import g_resources
    from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER

    if use_ready is None and (type(previous_count) is not int or previous_count < 1):
        raise ValueError("普通消耗品缺少使用前数量，未提交使用")

    def check():
        """在定位后的每次识图与点击前响应中止。"""
        if control is not None:
            control.check()

    def click(x, y, consume=False):
        """消费点击与中止共用锁，其他点击仅进入FAA动作队列。"""
        check()
        action = lambda: T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=faa.handle, x=int(x), y=int(y))
        if consume and control is not None:
            control.commit_click(action)
        else:
            action()

    selected_point = tuple(point)
    click(*selected_point)
    deadline = time.monotonic() + 1
    found = False
    for _check_index in range(25):
        check()
        time.sleep(.04)
        if time.monotonic() > deadline:
            break
        for name in ("物品-背包-使用.png", "物品-背包-使用-被选中.png"):
            status, point = match_p_in_w(
                source_handle=faa.handle, source_root_handle=faa.handle_360,
                source_range=[466, 86, 950, 500], template=g_resources.RESOURCE_P["item"][name],
                match_tolerance=.98)
            if status == 0:
                raise RuntimeError("使用按钮识别出错，未提交消耗品")
            if status == 2:
                if use_ready is not None:
                    time.sleep(.02)
                click(point[0] + 466, point[1] + 86, consume=True)
                found = True
                break
        if found:
            break
    if not found:
        raise RuntimeError("定向道具没有使用按钮，未重试或使用其他物品")
    # 使用菜单退出可能早于服务器奖励，固定等待后查不到X不代表本次已完成。
    # 普通物品等实际奖励或数量变化；没有奖励的增益道具仍可按扣减继续。
    if use_ready is None:
        deadline = time.monotonic() + 3
        for _check_index in range(75):
            check()
            time.sleep(.04)
            image = capture_image_png(handle=faa.handle, root_handle=faa.handle_360,
                                      raw_range=[0, 0, 950, 600])
            if find_bag_reward_close(image) is not None:
                break
            current = read_bag_item_count(image, selected_point)
            if current is not None and current != previous_count:
                break
            # 没有可确认变化交给会话的数量复核；连续三次明确未减少才提示道具栏满。
            if time.monotonic() >= deadline:
                break
    else:
        deadline = time.monotonic() + 10
        for _check_index in range(250):
            check()
            time.sleep(.04)
            if time.monotonic() >= deadline:
                raise RuntimeError("单次道具使用10秒未收到完成画面，不重试；请查看游戏现场")
            if use_ready(faa, tuple(targets), selected_point):
                time.sleep(.02)
                break
        else:
            raise RuntimeError("单次道具使用10秒/250轮未收到完成画面，不重试；请查看游戏现场")
    close_bag_reward_windows(faa, control)
    return 1


def read_bag_item_count(image, point):
    """读取指定装备格的数量；真实空格返回0，数字残缺返回None。

    Args:
        image: 完整游戏BGR/BGRA截图。
        point: 九列49px网格的格心，等于格子左上角加(24, 24)。

    Returns:
        int | None: 实际数量；没有数字描边的已知物品记1，不猜测残缺数字。
    """
    from function.globals import g_resources

    left, top = int(point[0]) - 24, int(point[1]) - 24
    if image is None or top < 0 or left < 0 or image.shape[0] < top + 44 or image.shape[1] < left + 47:
        return None
    if equipment_cell_empty(image, left, top):
        return 0
    # 装备栏相对合成屋数字右移2px、下移1px；两处共用8×6白字模板。
    block = image[top + 1:top + 50, left + 2:left + 51, :3]
    region = block[33:43, 9:45]
    outline = np.all(region == [72, 35, 13], axis=2) | np.all(region == [0, 0, 255], axis=2)
    if not outline.any():
        return 1
    left_edge = int(np.where(outline)[1].min()) + 9
    digits = []
    for place in range(5):
        x = 38 - place * 7
        if x + 6 <= left_edge:
            break
        white = np.all(block[34:42, x:x + 6] >= 250, axis=2)
        if white.shape != (8, 6) or not white.any():
            return None
        matches = []
        for digit in range(10):
            template = g_resources.RESOURCE_P["number"][f"{digit}.png"]
            mask = np.all(template[:, :, :3] >= 250, axis=2)
            if np.all(white[mask]):
                matches.append(digit)
        if not matches:
            return None
        digits.append(max(matches))
    return sum(digit * 10 ** place for place, digit in enumerate(digits)) if digits else 1


def _wait_bag_count(faa, point, control=None, previous=None, *, templates=None, name=None):
    """最多3秒核对原物品身份和数量；最后一件被新图标替代时结束旧堆，不重发或误用新物品。"""
    from function.common.bg_img_screenshot import capture_image_png

    deadline = time.monotonic() + 3
    replaced = None
    for attempt in range(75):
        if control is not None:
            control.check()
        time.sleep(.04)
        image = capture_image_png(handle=faa.handle, root_handle=faa.handle_360, raw_range=[0, 0, 950, 600])
        left, top = int(point[0]) - 24, int(point[1]) - 24
        if templates is not None and not equipment_cell_empty(image, left, top):
            block = image[top:top + 49, left:left + 49]
            if not templates.matches(block, name):
                # 最后一件消耗后，礼包奖励或前移物品可立即填回原格；新图标的数量不属于旧堆。
                # 只在原堆恰为1且替代图案连续两帧一致时记旧堆耗尽，绝不沿用坐标使用新物品。
                signature = block[:, :, :3].tobytes()
                if previous == 1 and signature == replaced:
                    return 0
                replaced = signature
                if time.monotonic() >= deadline:
                    break
                continue
        replaced = None
        count = read_bag_item_count(image, point)
        if count is None:
            if time.monotonic() >= deadline:
                break
            continue
        if previous is None or count < previous:
            return count
        if count > previous:
            raise RuntimeError("物品数量意外增加或格位已变化，已停止使用")
        if attempt == 74 or time.monotonic() >= deadline:
            return count
    raise RuntimeError("物品图标或数量3秒内无法识别，已停止使用；未知数量不按0或未减少处理")


class _BagUseSession:
    """每种物品独立计量；成功扣减清除失败计数，连续三次未减少停止整次调用。"""

    def __init__(self, faa, items, control=None, use_checker=None, use_ready=None, *, templates=None):
        self.faa, self.items, self.control = faa, items, control
        self.use_checker, self.use_ready = use_checker, use_ready
        self.templates = templates
        self.used = dict.fromkeys(items, 0)
        self.failures = dict.fromkeys(items, 0)
        self.attempts = dict.fromkeys(items, 0)
        self.submitted, self.blocked = 0, False

    def pending(self, name):
        """数量指确认消耗量；三次失败退出保证尝试总数不超过需求量的三倍。"""
        return not self.blocked and self.used[name] < self.items[name] and self.attempts[name] < self.items[name] * 3

    def use(self, name, point):
        """只在扣减确认后记成功，调用方可用返回的剩余量判断堆叠是否耗尽。"""
        identity = {"templates": self.templates, "name": name} if self.templates is not None else {}
        previous = _wait_bag_count(self.faa, point, self.control, **identity)
        if previous == 0:
            return 0
        _use_selected_bag_consumable(
            self.faa, (name,), point, control=self.control, use_ready=self.use_ready, previous_count=previous)
        self.submitted += 1
        self.attempts[name] += 1
        current = _wait_bag_count(self.faa, point, self.control, previous, **identity)
        if current == previous:
            self.failures[name] += 1
            if self.failures[name] == 3:
                from function.globals import SIGNAL
                from function.globals.log import CUS_LOGGER

                self.blocked = True
                message = (f"{getattr(self.faa, 'player', '')}P连续3次使用物品后数量未减少，道具栏可能已满。"
                           "已放弃本次所有物品的使用，请清理道具栏后重试。")
                CUS_LOGGER.warning(f"[背包] [使用停止] {name}：{message}")
                if SIGNAL.DIALOG is not None:
                    SIGNAL.DIALOG.emit(title="物品使用已停止", text=message)
            return current
        if current != previous - 1:
            raise RuntimeError("单次物品扣减不是1个，已停止使用")
        if self.use_checker is not None:
            for _ in range(75):
                if self.control is not None:
                    self.control.check()
                time.sleep(.04)
                if self.use_checker(self.faa, (name,), tuple(point)):
                    if self.use_ready is not None:
                        time.sleep(.02)
                    break
            else:
                raise RuntimeError("道具扣减后的记账3秒未确认，已停止使用")
        self.used[name] += 1
        self.failures[name] = 0
        return current


def _validate_bag_items(items, scan_only):
    """所有入口使用同一种物品数量字典，扫描只能传0，布尔值不作为次数。"""
    if (type(scan_only) is not bool or not isinstance(items, dict) or not items or
            any(not isinstance(name, str) or not name.strip() or type(count) is not int or count < 0
                for name, count in items.items()) or scan_only and any(items.values())):
        raise ValueError("物品白名单必须为非空的名称→非负数量字典；仅扫描时所有数量必须为0")


def use_targeted_consumables(faa, items, *, scan_only=False, inventory_reader=None,
                             item_locator=None, use_checker=None, control=None, inventory_sorter=None,
                             use_ready=None):
    """按各物品独立数量执行库存回调模式，最多三轮整理、扫描及使用，共享额度。

    Args:
        faa: 提供背包入口、退出及窗口句柄的FAA对象。
        items: 物品名称到使用数量的字典；仅扫描时每项为0。
        scan_only: 只整理并扫描，不选择物品。
        inventory_reader: 接受FAA对象的完整库存扫描回调。
        item_locator: 接受FAA对象及当前物品单元素白名单，返回49px格心或None。
        use_checker: 扣减确认后更新调用方位置记忆的回调，不代替实际数量识别。
        control: 可选中止对象，已提交的单次使用仍完成核准。
        inventory_sorter: 可选整理及位置记忆失效回调。
        use_ready: 可选奖励完成判定，最多等待10秒。

    Returns:
        ConsumableReport: 使用前后实测库存、提交次数、确认扣减次数和是否因未减少退出。

    Raises:
        ValueError: 字典或必要回调不完整，未打开背包。
        RuntimeError: 导航、数量、奖励或记账无法确认，不继续提交。
    """
    _validate_bag_items(items, scan_only)
    if (not callable(inventory_reader) or not scan_only and (
            not callable(item_locator) or not callable(use_checker)) or
            inventory_sorter is not None and not callable(inventory_sorter) or
            use_ready is not None and not callable(use_ready)):
        raise ValueError("定向消耗品需要完整库存扫描、定位及记账接口")
    def check():
        """导航和批末实扫前响应中止。"""
        if control is not None:
            control.check()

    check()
    if not faa.action_bottom_menu("背包"):
        raise RuntimeError("FAA背包入口未成功，未使用消耗品")
    session = _BagUseSession(faa, items, control, use_checker, use_ready)
    before = after = ()
    for round_index in range(1 if scan_only else 3):
        check()
        (inventory_sorter or sort_equipment_inventory)(faa, control)
        stock = tuple(inventory_reader(faa))
        if any(item.name in items and (type(item.count) is not int or item.count < 0) for item in stock):
            raise RuntimeError("指定物品数量未知，不能将它当作不存在或0")
        if round_index == 0:
            before = stock
        after = stock
        if scan_only:
            break
        available = {item.name for item in stock if item.name in items and
                     type(item.count) is int and item.count > 0 and session.pending(item.name)}
        if not available:
            break
        for name in items:
            if name not in available:
                continue
            while session.pending(name):
                if control is not None and control.requested.is_set():
                    break
                check()
                point = item_locator(faa, (name,))
                if point is None or session.use(name, point) == 0:
                    break
            if session.blocked or control is not None and control.requested.is_set():
                break
        if session.blocked or control is not None and control.requested.is_set() or not any(
                session.pending(name) for name in items):
            after = tuple(inventory_reader(faa))
            break
        if round_index == 2:
            after = tuple(inventory_reader(faa))
    check()
    faa.action_exit("普通红叉")
    return ConsumableReport(before, after, session.submitted, sum(session.used.values()), session.blocked)


@dataclass(frozen=True)
class _BagRow:
    top: int
    cells: tuple
    signature: bytes


@dataclass(frozen=True)
class _BagPage:
    phase: int
    top: int
    bottom: int
    rows: tuple


class _BagTemplates:
    """格内模板定位：常规比较使用与模板等大的区域，首次命中后记住裁剪位置。

    位置缓存只表示图标在49px格内的偏移，不表示物品已找全；每一格仍检查所有模板。
    """

    def __init__(self, images):
        from function.globals import g_resources

        self.entries, self.origins, self.calibrated = {}, {}, set()
        for name, template in images.items():
            mask = (g_resources.RESOURCE_P["item"]["物品-掩模-不绑定.png"]
                    if template.shape[:2] == (44, 44) else None)
            self.entries[name] = (template, mask)
            height, width = template.shape[:2]
            self.origins[name] = (1, 1) if (height, width) == (44, 44) else (
                (49 - width) // 2, (49 - height) // 2)

    def matches(self, block, name):
        """逐格核对模板；小尺寸特征首次允许在一格内定位，不能在整页任意匹配。"""
        from function.common.bg_img_match import match_p_in_w

        template, mask = self.entries[name]
        height, width = template.shape[:2]
        x, y = self.origins[name]
        region = block[y:y + height, x:x + width]
        if region.shape[:2] != (height, width):
            return False
        status, _point = match_p_in_w(
            source_img=region, template=template, mask=mask, return_center=False,
            match_tolerance=.99 if mask is not None else .98)
        if status == 0:
            raise RuntimeError("物品模板匹配失败")
        if status == 2:
            self.calibrated.add(name)
            return True
        if name in self.calibrated or block.shape[:2] == template.shape[:2]:
            return False
        status, point = match_p_in_w(
            source_img=block, template=template, mask=mask, return_center=False,
            match_tolerance=.99 if mask is not None else .98)
        if status == 0:
            raise RuntimeError("物品模板匹配失败")
        if status == 2:
            self.origins[name] = tuple(point)
            self.calibrated.add(name)
            return True
        return False


class _BagPages:
    """按格线、滑块和重合行遍历装备栏；扫描不会把重合页的同一堆计两次。"""

    def __init__(self, faa, templates, control=None, *, recognize_items=True):
        self.faa, self.control = faa, control
        self.templates = templates if isinstance(templates, _BagTemplates) else _BagTemplates(templates)
        self.recognize_items = recognize_items
        self.rows, self.offset, self.first_phase = {}, 0, None

    def check(self):
        if self.control is not None:
            self.control.check()

    def capture(self):
        """复用FAA截图；模板只比较道具图案，数字和绑定分别读取。"""
        from function.common.bg_img_screenshot import capture_image_png

        self.check()
        image = capture_image_png(handle=self.faa.handle, root_handle=self.faa.handle_360,
                                  raw_range=[0, 0, 950, 600])
        tops = equipment_row_tops(image)
        if not tops:
            raise RuntimeError("装备栏格线未确认")
        strip = image[108:413, 918, :3]
        indices = np.flatnonzero(np.max(np.abs(strip.astype(int) - [113, 73, 5]), axis=1) > 3)
        if not len(indices) or len(indices) != indices[-1] - indices[0] + 1:
            raise RuntimeError("装备栏滑块未确认")
        rows = []
        for top in tops:
            cells = []
            for column in range(9):
                left = 466 + 49 * column
                if equipment_cell_empty(image, left, top, include_unopened=True):
                    cells.append(BagItem(None, 0, None, True))
                    continue
                block = image[top:top + 49, left:left + 49]
                if not self.recognize_items:
                    cells.append(BagItem(None, None, None))
                    continue
                found = [name for name in self.templates.entries if self.templates.matches(block, name)]
                if len(found) > 1:
                    raise RuntimeError("同一格命中多个物品模板，未选择物品")
                count = read_bag_item_count(image, (left + 24, top + 24)) if found else None
                if found and count is None:
                    raise RuntimeError("指定物品数量未确认")
                binding = block[34:36, 4:6, :3]
                pink = np.all(binding == [156, 43, 255], axis=2)
                bound = True if pink.all() else None if pink.any() else False
                cells.append(BagItem(found[0] if found else None, count, bound))
            # 未知图标也参加重合校验，已知数字变化则由cells体现；不以未识别作为空格。
            signature = image[top + 10:top + 33, 466:907, :3].tobytes()
            rows.append(_BagRow(top, tuple(cells), signature))
        return _BagPage(tops[0], 108 + int(indices[0]), 109 + int(indices[-1]), tuple(rows))

    def wait(self, predicate=lambda _page: True):
        """画面连续两次一致且通过判定才继续，过渡帧最多重查3秒，不重发翻页。"""
        stable = None
        deadline = time.monotonic() + 3
        for _ in range(75):
            self.check()
            time.sleep(.04)
            try:
                page = self.capture()
                if page == stable and predicate(page):
                    return page
                stable = page
            except RuntimeError:
                stable = None
            if time.monotonic() >= deadline:
                break
        raise RuntimeError("装备栏3秒内无法确认完整视图，已停止操作")

    def merge(self, page, replace_current=False):
        """同一绝对行只保留一份；消费后的原页可更新，翻页重合处必须完全一致。"""
        for row in page.rows:
            index, remainder = divmod(self.offset + row.top - self.first_phase, 49)
            if remainder or index < 0:
                raise RuntimeError("装备行坐标不连续")
            old = self.rows.get(index)
            if old is not None and not replace_current and (old.cells, old.signature) != (row.cells, row.signature):
                raise RuntimeError("装备重合行内容变化，不能返回重复计数的库存")
            self.rows[index] = row

    def advance(self, old, page):
        """滑块位移只用于筛选，实际前进量必须与格线相位和整行重合共同吻合。"""
        bar_delta = page.top - old.top
        if bar_delta <= 0 or abs((page.bottom - page.top) - (old.bottom - old.top)) > 1:
            return False
        candidates = []
        for delta in range((old.phase - page.phase) % 49, 6 * 49 + 1, 49):
            if not delta or abs((old.bottom - old.top) * delta / (7 * 49) - bar_delta) > 2:
                continue
            overlaps, valid = 0, True
            for row in page.rows:
                index, remainder = divmod(self.offset + delta + row.top - self.first_phase, 49)
                previous = self.rows.get(index)
                if remainder or index < 0:
                    valid = False
                    break
                if previous is not None:
                    overlaps += 1
                    if (previous.cells, previous.signature) != (row.cells, row.signature):
                        valid = False
                        break
            if valid and overlaps:
                candidates.append(delta)
        if len(candidates) != 1:
            return False
        return candidates[0]

    def iterate(self, scan_only):
        """从顶端遍历；仅无消费的扫描可按整理后的连续空尾提前结束。"""
        from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER

        page = self.wait()
        for _ in range(3):
            if page.top == 108:
                break
            T_ACTION_QUEUE_TIMER.add_click_to_queue(
                handle=self.faa.handle, x=918, y=98 if page.top <= 110 else 109)
            page = self.wait()
        if page.top != 108:
            raise RuntimeError("未确认装备栏顶部，不能建立背包总视图")
        self.first_phase = page.phase
        self.merge(page)
        for _ in range(100):
            yield page
            cells = [item for row in page.rows for item in row.cells]
            if (scan_only and any(item.empty for item in cells) and
                    all(item.empty for item in cells[next(i for i, item in enumerate(cells) if item.empty):])):
                if sorted(self.rows) != list(range(len(self.rows))):
                    raise RuntimeError("装备扫描存在缺行，未返回部分库存")
                return
            if page.bottom == 413:
                if sorted(self.rows) != list(range(len(self.rows))):
                    raise RuntimeError("装备扫描存在缺行，未返回部分库存")
                return
            # 消费只改内容，不改滚动位置；将本页的真实扣减合入重合校验基线。
            updated = page if scan_only else self.wait(
                lambda view: (view.top, view.bottom, view.phase) == (page.top, page.bottom, page.phase))
            if not scan_only:
                self.merge(updated, replace_current=True)
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.faa.handle, x=918, y=min(page.bottom + 2, 412))
            next_page = self.wait(lambda view: bool(self.advance(updated, view)))
            self.offset += self.advance(updated, next_page)
            self.merge(next_page)
            page = next_page
        raise RuntimeError("装备栏翻页超过100次，未返回不完整库存")


    def scan(self):
        """整理后只扫描一次，返回按绝对行排列的九列内存视图，保留未知格和全部堆叠。"""
        for _page in self.iterate(True):
            pass
        result = tuple(self.rows[index] for index in range(len(self.rows)))
        cells = [item for row in result for item in row.cells]
        if any(item.empty for item in cells) and not all(
                item.empty for item in cells[next(index for index, item in enumerate(cells) if item.empty):]):
            raise RuntimeError("整理后的空格后仍有物品，未返回不完整库存")
        return result

    def verify(self, name, point):
        """使用快照位置前只核对当前一格，避免整理后的旧坐标或图标变化造成误用。"""
        from function.common.bg_img_screenshot import capture_image_png

        deadline = time.monotonic() + 3
        for _ in range(75):
            self.check()
            time.sleep(.04)
            image = capture_image_png(handle=self.faa.handle, root_handle=self.faa.handle_360,
                                      raw_range=[0, 0, 950, 600])
            left, top = point[0] - 24, point[1] - 24
            if self.templates.matches(image[top:top + 49, left:left + 49], name):
                return
            if time.monotonic() >= deadline:
                break
        raise RuntimeError("待使用格子的图标与本轮背包快照不符，已停止使用")


def _use_named_bag_consumables(faa, items, scan_only=False, control=None, bound_only=False):
    """每轮先整理、扫描完整占用前缀再使用，最多三轮共享同一份物品额度。"""
    from function.globals import g_resources

    images = {}
    for name in items:
        image = g_resources.RESOURCE_P.get("item", {}).get(name)
        if image is None:
            image = g_resources.RESOURCE_CP.get("背包_装备_需使用的", {}).get(name)
        if image is None or isinstance(image, dict):
            raise ValueError(f"缺少指定消耗品模板：{name}")
        images[name] = image
    if not scan_only and not any(items.values()):
        return dict.fromkeys(items, 0)
    templates = _BagTemplates(images)
    if control is not None:
        control.check()
    if not faa.action_bottom_menu(mode="背包"):
        raise RuntimeError("FAA背包入口未成功，未使用指定消耗品")
    # 图标首次进入时异步加载；同一次背包会话的后续轮次不重复这段等待。
    time.sleep(10)
    session = _BagUseSession(faa, items, control, templates=templates)

    def stopping():
        """在途物品核准后退出，不继续翻页、整理或选择下一物品。"""
        return control is not None and control.requested.is_set()

    for _round in range(1 if scan_only else 3):
        if stopping():
            break
        sort_equipment_inventory(faa, control)
        scanner = _BagPages(faa, templates, control)
        snapshot = scanner.scan()
        if scan_only:
            result = dict.fromkeys(items, 0)
            for row in snapshot:
                for item in row.cells:
                    if item.name in items and (not bound_only or item.bound is True):
                        result[item.name] += item.count
            faa.action_exit(mode="普通红叉")
            return result
        planned = {(index, column): item for index, row in enumerate(snapshot)
                   for column, item in enumerate(row.cells)
                   if item.name in items and session.pending(item.name) and
                   (not bound_only or item.bound is True)}
        if not planned:
            break
        # 消费阶段只读格线、滑块和当前图案用于位移核验；使用对象来自本轮完整快照。
        viewer = _BagPages(faa, templates, control, recognize_items=False)
        for page in viewer.iterate(False):
            for row in page.rows:
                index, remainder = divmod(viewer.offset + row.top - viewer.first_phase, 49)
                if remainder:
                    raise RuntimeError("消费视图与背包行号无法对齐，未点击物品")
                for column in range(len(row.cells)):
                    item = planned.pop((index, column), None)
                    if item is None or not session.pending(item.name):
                        continue
                    point = (490 + 49 * column, row.top + 24)
                    viewer.verify(item.name, point)
                    while session.pending(item.name) and not stopping():
                        if session.use(item.name, point) == 0:
                            break
                    if session.blocked or stopping():
                        break
                if session.blocked or stopping():
                    break
            if session.blocked or stopping() or not any(session.pending(item.name) for item in planned.values()):
                break
        if session.blocked or stopping() or not any(session.pending(name) for name in items):
            break
        # 新物品可能填到已用完的前方格子；下一轮重新整理并扫描，不能把当前快照当最终库存。
    if control is not None:
        control.check()
    faa.action_exit(mode="普通红叉")
    return session.used


def use_bag_consumables(faa, items=None, *, scan_only=False,
                        inventory_reader=None, item_locator=None, use_checker=None, control=None,
                        inventory_sorter=None, use_ready=None):
    """按数量字典使用或扫描背包，最多三轮共享额度；默认使用配置中的绑定物品，每种最多999个。

    Args:
        faa: 提供FAA导航、窗口句柄及日志的对象。
        items: 物品名称到使用数量的字典，例如{"A.png": 3, "B.png": 6}。
            数量是确认消耗量；999只是有限上限，不表示无限。省略时使用配置白名单。
        scan_only: 为True时每项数量必须为0，只返回扫描结果。
        inventory_reader: 专用调用可复用已有完整库存扫描回调。
        item_locator: 专用定位回调，返回49px格心坐标。
        use_checker: 实际扣减后更新专用记忆的回调。
        control: 可选中止对象。
        inventory_sorter: 专用整理及位置记忆失效回调。
        use_ready: 专用奖励完成判定，最多10秒。

    Returns:
        dict | ConsumableReport: 普通使用返回确认消耗量字典，普通扫描返回实际库存字典；
            带库存回调时返回使用前后实扫及提交、确认数量报告。
            任意物品连续三次未减少都会弹窗并提前结束整次调用。

    Raises:
        ValueError: 非法字典、扫描数量不为0、模板缺失或专用回调不完整。
        RuntimeError: 识图、数量变化或使用结果无法确认；未知数量不作为未减少重试。
    """
    from function.globals import g_resources

    bound_only = items is None
    if items is None:
        if scan_only or any(callback is not None for callback in (
                inventory_reader, item_locator, use_checker, control, inventory_sorter, use_ready)):
            raise ValueError("定向消耗品参数缺少物品白名单字典")
        items = {name: 999 for name in g_resources.RESOURCE_CP.get("背包_装备_需使用的", {})}
        if not items:
            return {}
    _validate_bag_items(items, scan_only)
    if any(callback is not None for callback in (
            inventory_reader, item_locator, use_checker, inventory_sorter, use_ready)):
        return use_targeted_consumables(
            faa, items, scan_only=scan_only, inventory_reader=inventory_reader, item_locator=item_locator,
            use_checker=use_checker, control=control, inventory_sorter=inventory_sorter, use_ready=use_ready)
    return _use_named_bag_consumables(faa, items, scan_only, control, bound_only)
