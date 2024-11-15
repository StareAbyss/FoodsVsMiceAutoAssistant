import queue

from function.globals.log import CUS_LOGGER


class CardQueue(queue.PriorityQueue):
    def __init__(self, card_list, handle, handle_360):
        # 定义优先级队列
        super().__init__()
        self.card_list = card_list  # 包含除复制外的所有卡片的实例
        self.card_using = False
        self.handle = handle
        self.handle_360 = handle_360

    # 初始化card队列
    def init_card_queue(self, game_image=None):

        for card in self.card_list:
            # 更新 status_ban
            if card.status_ban > 0:
                card.status_ban -= 1

            # 更新卡片状态
            card.fresh_status(game_image=game_image)

            # 重新装填卡片入队, 幻坤除外
            self.put((card.set_priority, card))

    def put_card_queue(self, card):
        self.put((card.set_priority, card))

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

        # 处于卡片使用状态 直接返回
        if self.card_using:
            return

        self.card_using = True

        # 查看队列顶部的元素
        card = self.peek()[1]

        # 卡片没有需要放置的位置 如果该卡正好是全新的卡背+没有可放置位置 会卡死 所以只要没有可放位置就移出队列
        if not card.coordinate_to:
            self.get()
            self.card_using = False
            return

        # 如果这张卡被锁 移出队列
        if card.status_ban > 0:
            self.get()
            self.card_using = False
            return

        # 未知卡片状态图 使用它(无限使用 直至更高顺位卡片完成冷却, 或成功获得状态)
        if card.state_images["冷却"] is None:
            try_result = card.try_get_img_for_check_card_states()
            if try_result == 2:
                # 试色成功 移出队列 (已经完成使用)
                self.get()
                self.card_using = False
                return
            if try_result == 1:
                # 直接读取成功 获取状态
                card.fresh_status()
            if try_result == 0:
                # 读取和试色均失败. 堵在此处
                self.card_using = False
                return

        # 如果卡片在cd中 移出队列
        if card.status_cd:
            self.get()
            self.card_using = False
            return

        # 去使用这张卡
        card.use_card()
        self.card_using = False
