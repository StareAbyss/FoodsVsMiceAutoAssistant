import time
from typing import TYPE_CHECKING

from function.common.bg_img_match import loop_match_p_in_w, match_ps_in_w
from function.globals.g_resources import RESOURCE_P
from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER

if TYPE_CHECKING:
    from function.core.faa.faa_mix import FAA


class FAASynthesis:

    # 强卡模拟器 新建文件夹ing

    def disenchant_gem(self: "FAA"):
        """
        宝石分解
        """

        self.action_bottom_menu(mode="合成屋")

        # 等待加载
        time.sleep(5)

        # 切换到对应界面
        loop_match_p_in_w(
            source_handle=self.handle,
            source_root_handle=self.handle_360,
            source_range=[420, 385, 495, 485],
            template=RESOURCE_P["synthesis"]["宝石分解_未选中.png"],
            match_tolerance=0.99,
            match_interval=0.2,
            match_failed_check=2,
            after_sleep=3,
            click=True,
            after_click_template=RESOURCE_P["synthesis"]["宝石分解_选中.png"],
        )

        while True:

            source_range = [558, 89, 903, 532]
            gem_ps = RESOURCE_P["synthesis"]["可分解宝石"]
            result = match_ps_in_w(
                source_handle=self.handle,
                source_root_handle=self.handle_360,
                template_opts=[
                    {"template": gem_ps["攻击宝石.png"], "source_range": source_range, "match_tolerance": 0.98},
                    {"template": gem_ps["猫眼宝石.png"], "source_range": source_range, "match_tolerance": 0.98},
                    {"template": gem_ps["绿宝石.png"], "source_range": source_range, "match_tolerance": 0.98},
                    {"template": gem_ps["对战雾宝石.png"], "source_range": source_range, "match_tolerance": 0.98},
                    {"template": gem_ps["神圣宝石.png"], "source_range": source_range, "match_tolerance": 0.98},
                    {"template": gem_ps["对战轰炸宝石.png"], "source_range": source_range, "match_tolerance": 0.98},
                    {"template": gem_ps["轰炸宝石.png"], "source_range": source_range, "match_tolerance": 0.98},
                    {"template": gem_ps["冰冻宝石.png"], "source_range": source_range, "match_tolerance": 0.98},
                    {"template": gem_ps["激光宝石.png"], "source_range": source_range, "match_tolerance": 0.98},
                ],
                return_mode='or',
                quick_mode=True
            )
            if result:
                # 点击选择
                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=self.handle,
                    x=result[0] + source_range[0],
                    y=result[1] + source_range[1])
                time.sleep(0.333)
            else:
                break

            # 点击分解
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=285, y=375)
            time.sleep(0.666)

        # 退出合成屋
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=915, y=40)
        time.sleep(1)
