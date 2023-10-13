# coding:utf-8
import sys
from time import sleep, strftime, localtime

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QApplication
from cv2 import imwrite, vconcat
import multiprocessing

from function.common.background_mouse import mouse_left_click
from function.common.background_screenshot import capture_picture_png
from function.common.background_screenshot_and_compare_picture import loop_find_p_in_p_ml_click
from function.script.common import FAA
from function.script.farm_ui import MyMainWindow


class Communicate(QObject):
    my_signal = pyqtSignal(dict)


class FVMMainWindow(MyMainWindow):
    def __init__(self, num_p):
        # 从父类构造方法
        super().__init__(num_p=num_p)

    def battle_all_round(self, p_id, dic_opt_battle):
        """
        一个账号的战斗进程
        Args:
            p_id: 进程id
            dic_opt_battle: 参数dic
        """
        activation = dic_opt_battle["activation"]
        channel = dic_opt_battle["channel"]
        battle_time_max = dic_opt_battle["battle_time_max"]  # 战斗次数
        use_key = dic_opt_battle["use_key"]
        use_card = dic_opt_battle["use_card"]

        if activation:
            fvm = FAA(channel=channel, dpi=1.5, use_key=use_key, auto_battle=use_card)
            for i in range(battle_time_max):
                # 进行一轮战斗
                self.battle_a_round(p_id=p_id, fvm=fvm)

    def battle_a_round(self, p_id, fvm):

        # 提取一些常用变量
        handle = fvm.handle
        dpi = fvm.dpi
        path_common = fvm.path_p_common
        path_logs = fvm.path_logs
        print(handle,dpi,path_common,path_logs)

        # 刷新ui: handle文本
        # if self.my_signal:
        #     self.my_signal.emit({"process_id": p_id, "key": "auto_handle", "value": handle})

        # 刷新ui: 状态文本
        # if self.my_signal:
        #     self.my_signal.emit({"process_id": p_id, "key": "process_status", "value": "寻找开始或准备按钮"})

        # 循环查找开始按键
        loop_find_p_in_p_ml_click(
            handle, path_common + "\\BattleBefore_ReadyCheckStart.png",
            change_per=dpi, sleep_time=0.3, click=False)

        # 获取关卡名称
        stage_name = fvm.get_stage_name()

        # 循环查找开始按键 点击
        loop_find_p_in_p_ml_click(
            handle, path_common + "\\BattleBefore_ReadyCheckStart.png",
            change_per=dpi, sleep_time=0.3, click=True)

        # 点一下潜在的确认可以不带某卡片
        mouse_left_click(handle, int(427 * dpi), int(353 * dpi))

        # 刷新ui: 状态文本
        # if self.my_signal:
        #     self.my_signal.emit({"process_id": p_id, "key": "process_status", "value": "等待进入战斗"})

        # 循环查找火苗图标 找到战斗开始
        loop_find_p_in_p_ml_click(
            handle, path_common + "\\Battle_FireElement.png",
            change_per=dpi, click=False)

        # 刷新ui: 状态文本
        # if self.my_signal:
        #     self.my_signal.emit({"process_id": p_id, "key": "process_status", "value": "战斗进行中..."})

        # 放人物
        fvm.battle_use_player("4-1")
        fvm.battle_use_player("4-2")
        fvm.battle_use_player("4-3")
        fvm.battle_use_player("4-4")

        # 战斗循环
        fvm.battle()

        # 刷新ui: 状态文本
        # if self.my_signal:
        #     self.my_signal.emit({"process_id": p_id, "key": "process_status", "value": "战斗结束 记录战利品"})

        # 记录战利品
        img = []
        mouse_left_click(handle, int(708 * dpi), int(484 * dpi), 0.05, 0.05)
        mouse_left_click(handle, int(708 * dpi), int(484 * dpi), 0.05, 0.3)
        img.append(capture_picture_png(handle)[453:551, 209:698])  # Y_min:Y_max,X_min:X_max
        sleep(0.5)
        mouse_left_click(handle, int(708 * dpi), int(510 * dpi), 0.05, 0.05)
        mouse_left_click(handle, int(708 * dpi), int(510 * dpi), 0.05, 0.3)
        img.append(capture_picture_png(handle)[453:552, 209:698])  # Y_min:Y_max,X_min:X_max
        sleep(0.5)
        mouse_left_click(handle, int(708 * dpi), int(527 * dpi), 0.05, 0.05)
        mouse_left_click(handle, int(708 * dpi), int(527 * dpi), 0.05, 0.3)
        img.append(capture_picture_png(handle)[503:552, 209:698])  # Y_min:Y_max,X_min:X_max
        # 垂直拼接
        img = vconcat(img)
        # 保存图片
        imwrite(
            "{}\\{}[{}].png".format(
                path_logs,
                stage_name,
                strftime('%Y-%m-%d_%Hh%Mm', localtime())
            ), img)

        # 刷新ui: 状态文本
        # if self.my_signal:
        #     self.my_signal.emit({"process_id": p_id, "key": "process_status", "value": "战斗结算中..."})

        # 循环查找战利品字样
        loop_find_p_in_p_ml_click(
            handle,
            path_common + "\\BattleEnd_Chest.png",
            change_per=dpi,
            click=False
        )

        # 刷新ui: 状态文本
        # if self.my_signal:
        #     self.my_signal.emit({"process_id": p_id, "key": "process_status", "value": "翻牌中..."})

        # 开始翻牌
        mouse_left_click(handle, int(708 * dpi), int(502 * dpi), 0.05, 4)
        # 翻牌
        mouse_left_click(handle, int(708 * dpi), int(370 * dpi), 0.05, 0.25)
        mouse_left_click(handle, int(708 * dpi), int(170 * dpi), 0.05, 0.25)
        # 结束翻牌
        mouse_left_click(handle, int(708 * dpi), int(502 * dpi), 0.05, 3)

        # 刷新ui: 状态文本
        # if self.my_signal:
        #     self.my_signal.emit({"process_id": p_id, "key": "process_status", "value": "战斗结束!"})

        # 战斗结束休息
        sleep(4)

    def run(self):
        dict_opt = {
            'activation': True,
            'use_key': True,
            'use_card': True,
            'battle_time_max': 10,
            'channel': '深渊之下 | 锑食'
        }
        p0 = multiprocessing.Process(target=self.battle_all_round, args=(0, dict_opt))
        p0.start()
        p0.join()



if __name__ == "__main__":
    def main():
        # 实例化 PyQt后台管理
        app = QApplication(sys.argv)

        fvm_m = FVMMainWindow(4)
        fvm_m.run()

        # 运行主循环，必须调用此函数才可以开始事件处理
        sys.exit(app.exec_())


    main()
