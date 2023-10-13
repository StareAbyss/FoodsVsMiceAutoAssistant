# coding:utf-8
import sys
from time import sleep, time, strftime, localtime

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QPushButton, QApplication, QLabel
from cv2 import imwrite, vconcat
import multiprocessing

from function_common.background_mouse import mouse_left_click
from function_common.background_screenshot import capture_picture_png
from function_common.background_screenshot_and_compare_picture import loop_find_p_in_p_ml_click

from script.common import FAA
from script.farm_ui import MyMainWindow


class Communicate(QObject):
    my_signal = pyqtSignal(dict)


class FVMMainWindow(MyMainWindow):
    def __init__(self, num_p):

        super().__init__(num_p)

        # # 定义信号槽
        self.c = Communicate()
        # # 将函数和信号槽绑定
        self.c.my_signal.connect(lambda: self.refresh_data)

    def battle_a_round(self, p_id: int, fvm: object):
        """
        一轮战斗
        Args:
            p_id:
            fvm:
        """

        # 提取一些常用变量
        handle = fvm.handle
        dpi = fvm.dpi
        path_common = fvm.path_common
        path_logs = fvm.path_logs

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
        stage_name = fvm.find_stage_name()

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

    def battle_all_round(self, p_id: int, dic_opt_battle: dict):
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
        print(1)

        if activation:
            fvm = FAA(channel=channel, dpi=self.dpi, use_key=use_key, auto_battle=use_card)
            time_flag = time()
            for i in range(battle_time_max):
                # 进行一轮战斗
                self.battle_a_round(p_id=p_id, fvm=fvm)
                # 刷新ui: 战斗时间和次数
                # if self.my_signal:
                #     self.my_signal.emit({"process_id": p_id,
                #                          "key": "completed_count",
                #                          "value": i + 1
                #                          })
                #     self.my_signal.emit({"process_id": p_id,
                #                          "key": "completed_used_time",
                #                          "value": round(time() - time_flag)
                #                          })
                time_flag = time()

        # 刷新ui: 状态文本
        # if self.my_signal:
        #     self.my_signal.emit({"process_id": p_id, "key": "process_status", "value": "结束\nEnd"})

    def click_btn_start(self, button):
        """
        开始/结束按钮 需要注册的函数
        Args:
            button: 被注册的按钮对象
        """
        p_id = int((int(button.sender().objectName()[2]) - 1) / 2)

        # 先刷新数据
        self.refresh_process_parameter(p_id)

        if not self.dic_p["flag_activation"][p_id]:
            # 创建 储存 启动进程
            print([p_id, self.dic_p["dic_process_opt"][p_id]])
            self.dic_p["process"][p_id] = multiprocessing.Process(
                target=self.battle_all_round,
                args=(p_id, self.dic_p["dic_process_opt"][p_id])
            )
            print(self.dic_p["process"][p_id])
            self.dic_p["process"][p_id].start()
            # 设置按钮文本
            button.sender().setText("终止\nEnd")
            # 设置flag
            self.dic_p["flag_activation"][p_id] = True
        else:
            # 中止进程
            # if self.dic_p["process"][p_id].is_alive():  # 判断进程是否还在运作中
            #     self.dic_p["process"][p_id].terminate()  # 中断进程
            #     self.dic_p["process"][p_id].join()  # 清理僵尸进程
            # 设置按钮文本
            button.sender().setText("开始\nLink Start")
            # 设置进程状态文本
            self.findChild(QLabel, "E_{}_7_2".format(p_id * 2 + 1)).setText("已中断进程")
            # 设置flag
            self.dic_p["flag_activation"][p_id] = False


if __name__ == "__main__":
    def main():
        # 进程总数
        num_process = 4

        # 实例化 PyQt后台管理
        app = QApplication(sys.argv)

        # 实例化 主窗口
        fvm_main_window = FVMMainWindow(num_process)

        # 建立槽连接 注意 多线程中 槽连接必须写在主函数
        # 注册函数：开始/结束按钮
        for p_id in range(fvm_main_window.num_process):
            button = fvm_main_window.findChild(QPushButton, "E_{}_7_1".format(p_id * 2 + 1))
            button.clicked.connect(lambda: fvm_main_window.click_btn_start(button))

        # 主窗口 现实
        fvm_main_window.show()

        # 运行主循环，必须调用此函数才可以开始事件处理
        sys.exit(app.exec_())


    main()
