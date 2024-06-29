import queue

from function.globals.extra import EXTRA_GLOBALS
from function.globals.log import CUS_LOGGER


class CardQueue(queue.PriorityQueue):
    def __init__(self, card_list):
        # 定义优先级队列
        super().__init__()
        self.card_list = card_list
        self.card_using = False

    # 初始化card队列
    def init_card_queue(self):

        for card in self.card_list:
            # 更新 status_ban
            card.status_ban -= 1
            if card.status_ban < 0:
                card.status_ban = 0

            # 更新 cd情况
            card.fresh_status()

            # 重新装填卡片入队, 幻坤除外
            self.put((card.priority, card))

    def put_card_queue(self, card):
        self.put((card.priority, card))

    def peek(self):
        card_tuple = self.get()
        self.put((card_tuple[0], card_tuple[1]))
        return card_tuple

    def print_self(self):
        # 由于我们不能直接遍历PriorityQueue，我们需要先将其转换为列表
        # 注意：这将会破坏队列，因为get()操作会从队列中移除元素
        items = []
        items_name = []
        while not self.empty():
            priority, item = self.get()
            # 保存元素以便之后恢复队列
            items.append((priority, item))
            items_name.append(item.name)
        # 恢复队列的原始状态
        for priority, item in items:
            self.put((priority, item))
        CUS_LOGGER.debug(items_name)

    def use_top_card(self):

        if self.card_using:
            return
        self.card_using = True

        card = self.peek()[1]
        card.fresh_status()

        if card.status_ban != 0:
            # 如果这张卡被锁了 直接滚出去
            self.get()
            self.card_using = False
            return

        if not card.status_usable:
            # 如果卡片不可用,且在cd中, 直接滚出去
            if card.status_cd:
                self.get()
            self.card_using = False
            return

        if EXTRA_GLOBALS.battle_extra_log:
            CUS_LOGGER.debug(f"[战斗执行器] 使用卡片：{card.name}")

        # 去使用这张卡
        card.use_card()
        self.card_using = False
