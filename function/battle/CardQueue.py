import queue
import time

from function.battle.Card import Card
from function.battle.get_position_in_battle import get_position_card_deck_in_battle
from function.script.FAA import FAA


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
            # 重新装填卡片入队
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
        # print(items_name)

    def use_top_card(self):

        if self.card_using:
            return
        # self.print_self()

        self.card_using = True
        card = self.peek()[1]
        card.fresh_status()

        if card.status_ban != 0:
            # 如果这张卡被锁了 直接滚出去
            self.get()
            self.card_using = False
            return

        if card.status_cd:
            # 如果这张还在冷却 直接滚出去
            self.get()
            self.card_using = False
            return

        # 去使用这张卡
        card.use_card()
        self.card_using = False


if __name__ == '__main__':
    def test():
        faa_1 = FAA(channel="锑食", zoom_rate=1)
        faa_2 = FAA(channel="锑食", zoom_rate=1)

        faa_1.set_config_for_battle(
            stage_id="NO-1-14",
            is_group=True,
            battle_plan_index=0)

        faa_2.set_config_for_battle(
            stage_id="NO-1-14",
            is_group=True,
            battle_plan_index=0)

        # 1.识图卡片数量，确定卡片在deck中的位置
        faa_1.bp_card = get_position_card_deck_in_battle(handle=faa_1.handle)
        faa_2.bp_card = get_position_card_deck_in_battle(handle=faa_2.handle)

        # 2.识图承载卡参数
        faa_1.init_mat_card_position()
        faa_2.init_mat_card_position()

        # 3.计算所有坐标
        faa_1.init_battle_plan_1()
        faa_2.init_battle_plan_1()

        # 4.刷新faa放卡实例
        faa_1.init_battle_object()
        faa_2.init_battle_object()

        card_list = []
        for j in range(len(faa_1.battle_plan_1["card"])):
            # 按从前到后顺序，作为优先级顺序，从0开始
            card_list.append(Card(faa=faa_1, priority=j))

        card_queue = CardQueue(card_list=card_list)
        card_queue.init_card_queue()

        for i in range(20):
            print(card_queue.peek()[1].name)
            card_queue.use_top_card()
            time.sleep(2)


    test()
