from PyQt6.QtWidgets import QMainWindow, QTextEdit, QVBoxLayout, QWidget

text = """\
轻度使用: 请读完 每章的 <卡组要求> 部分.
详细介绍: 有兴趣或者遇到相关问题可以细看.

一. 自动识别+放置
    
    * 卡组要求
        * 以下卡片仅需提前置于卡组末尾并保存, 战斗中将识别其位置并依据一定逻辑放置, 无需写入战斗方案.
        * 若强行在战斗方案中写入它们, 可能会导致放卡滞缓.
    
    * 承载卡
        * 在FAA中, 除自建房战斗中的所有关卡, 均适配有全自动的承载卡放置.
        * 支持所有转职的木盘子/棉花糖/麦芽糖/魔法软糖/苏打气泡, 暂不支持盘盘鸡&猫猫盘.
        * 双人战斗时, 两个角色将平分承载卡任务. 故小号也需要带上承载卡.
        * 若您发现部分关卡没有承载卡配置, 请通过以下方式解决问题.
            * FAA版本更新.
            * 交流群内获取资源, 手动更新至 "/config/stage_info_extra.json".
            * 如果图包和新版本也不包含, 请通过QQ或Github向开发者反馈.
        
    * 极寒冰沙
        * 检测到所有卡片均进入冷却(或放满被锁定)时, 自动放置.
        * 在双人战斗时, 会自动错开放置.
        * 需战斗中火苗数>=1000.
        
    * 幻幻鸡
        * 仅支持同时携带一张该类卡片(含转职和创造神).
        * 将根据 [战斗方案] 中为每张卡片设置的优先级 (坤参数) 进行自动复制
        * 坤参数为0不复制, 坤参数越高被复制优先级越高, 同优先级取卡片顺序.
        * 需战斗中火苗数>=1000.

二. 公会任务

    * 卡组要求
        * 任意卡组
            * 战斗方案的卡槽需求必须是连续的(即不能出现79但不使用卡槽8的情况), 默认的方案总是符合要求.
            * 战斗方案要求带卡之后留空一个格子, 预留给任务带卡.  
            * 之后携带的承载卡中, 必须包含气泡. 否则对应任务无法完成.
            * 可能的任务卡有: 油灯/双层小笼包/酒瓶炸弹/肥牛火锅/香肠/热狗大炮. 油灯可用原版和一转, 其他尽可用原版.
            
        * 在该空格之后, 再携带上文所述的自动识别的卡片. 
        
    * 额外带卡的任务
        * FAA 将在战斗前, 自动从您已有的绑定的卡片中携带它们, 并自动替换第七列的放卡以完成任务.
        * 这就是预留空格的原因.

三. 自动大赛

    * 卡组要求
        * 强制使用战斗方案 [1卡组-默认-1P] 和 [1卡组-默认-2P] 进行自动大赛功能.
        * 具体卡组和所有适配的所有同类替换卡如下(如不特别提及, 包含全部转职阶段), 如不说明可选则必须携带
            1. 产火 = 小火炉 & 花火龙 & 太阳神(白板/三转/四转)
            2. 海星 = 炭烧海星 & 猪猪搅拌器 & 陀螺喵 & 冥神(白板/三转/四转) & 查克拉兔
            3. 防空 = 糖葫芦炮弹 & 防空喵 & 大力神 & 火箭猪 & 大地女神
            4. 护罩 = 瓜皮护罩 & 处女座 & 暖炉汪 & 猫护罩 & 扑克牌护罩 & 祥龙环 & 赫拉(白板或三转)
            5. 对地 = 狮子座精灵 & 可乐汪 & 元气牛 & 冰冻冷萃机 & 冰晶龙 & 雪球兔 & 冰神(终转)
            6. 照明 = 油灯 & 肉松清明粿 & 防萤草
            7. 布丁 = 樱桃反弹布丁 & 艾草粑粑 & 布丁狗 & 布丁牛 & 水神(白板/三转/四转)
            8. 空格. 之后的卡片可以乱序携带
            木盘 = 木盘子 盘盘鸡 喵喵盘, 最多一种
            棉花 = 麦芽糖 棉花糖, 最多一种
            气泡
            咖啡粉(可选)
            魔法软糖(可选)
            冷却(可选) = 极寒冰沙(二转)
            复制(可选) = 幻幻鸡 & 创造神(白板/三转/四转)
    * 额外带卡的任务
        * 处理方式见上, 同公会任务.
        
    * 禁用卡片的任务
        * 对于禁用卡片的任务, FAA会自动移除指定卡片, 以完成任务要求. 
        * FAA能识别并移除的卡片资源请参见"/resource/image/card/准备房间/". 
          您可以使用在资源中命名相同的卡片进行替代. (例如:使用大力神->糖葫芦)
        * 请注意, 如果您替代了某些卡片, 部分需要某些卡片原名称对应卡片完成的任务, 将不会额外携带任务卡. 
          因此最好老实按照默认卡组的要求完成任务. 例如:使用大力神->糖葫芦, 任务要求使用糖葫芦, 任务将无法完成.
        * 这是强制战斗方案的原因.
        
    * 限制卡片数量的任务
        * FAA 通过对指定方案中卡片的重要性, 关卡是否需要承载等情况, 智能生成禁用卡片列表, 以完成该类任务. 
        * 如果您替代了某些卡片, 只要在FAA可识别卡片范围内进行互换, 并不会影响该类任务完成. 
          例如:使用大力神->糖葫芦, 任务要求仅使用三张卡, 除产火海星和麦芽糖都被ban了, 任务可以正常完成.
        * 这是强制战斗方案的原因.
        
    * 重复尝试
        * FAA 会对同一个未完成的任务尝试最多三次, 不会进行第四次尝试.
        * 这避免了因为FAA逻辑处理问题或号主配置不够无限循环的问题.
        * 也避免了部分任务无法完成的问题. 
            例1: 产火要求1w但号主没有月卡, 因为boss最终损卡+补卡而火不满失败. 
            例2: 部分要求杀敌数量任务打一次杀不完.
            
    * 识别方式     
        * 自动大赛使用 OCR文字识别 + 语义识别自动生成战斗方案. 
        * 因此即使不进行版本更新, 也能自动完成绝大部分任务. 
        * 部分任务识别不出, 请通过以下方式解决问题.
            * FAA版本更新.
            * 也可以在交流群内获取资源, 手动更新字库至 "/resource/image/ocr/美食大赛/".
            * 如果图包和新版本也不包含, 请通过QQ或Github向开发者反馈.
"""


class QMWTipBattle(QMainWindow):
    def __init__(self):
        super().__init__(parent=None)
        self.setWindowTitle('战斗逻辑介绍')
        self.text_edit = None
        # 设置窗口大小
        self.setFixedSize(850, 400)
        self.initUI()

    def initUI(self):
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)  # 设置为只读模式

        # 插入文本
        self.text_edit.setPlainText(text)

        # 设置布局
        layout = QVBoxLayout()
        layout.addWidget(self.text_edit)

        # 设置主控件
        main_widget = QWidget()
        main_widget.setLayout(layout)

        # 将 控件注册 为 窗口主控件
        self.setCentralWidget(main_widget)
