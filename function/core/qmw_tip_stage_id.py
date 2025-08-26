from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QMainWindow, QTableWidgetItem, QTableWidget, QVBoxLayout, QWidget


class QMWTipStageID(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("关卡代号一览 格式: 字母字母-数字-数字")
        # 设置窗口大小
        self.setFixedSize(900, 550)
        self.initUI()

    def initUI(self):

        table = QTableWidget()
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)  # 设置为不可编辑
        table.verticalHeader().setVisible(False)  # 隐藏行号
        table.horizontalHeader().setVisible(False)  # 隐藏列号
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)  # 禁用选择功能

        # 定义表头和对应的数据
        data_dict = {
            "美味岛": [
                ["曲奇岛", "NO-1-1"],
                ["色拉岛-陆", "NO-1-2"],
                ["色拉岛-水", "NO-1-3"],
                ["慕斯岛", "NO-1-4"],
                ["香槟岛-陆", "NO-1-5"],
                ["香槟岛-水", "NO-1-6"],
                ["神殿", "NO-1-7"],
                ["布丁岛-日", "NO-1-8"],
                ["布丁岛-夜", "NO-1-9"],
                ["可可岛-日", "NO-1-10"],
                ["可可岛-夜", "NO-1-11"],
                ["咖喱岛-日", "NO-1-12"],
                ["咖喱岛-夜", "NO-1-13"],
                ["深渊", "NO-1-14"],
                ["美味漫游", "NO-1-15"]
            ],
            "火山岛": [
                ["芥末小屋-日", "NO-2-1"],
                ["芥末小屋-夜", "NO-2-2"],
                ["薄荷海滩-日", "NO-2-3"],
                ["薄荷海滩-夜", "NO-2-4"],
                ["芝士城堡", "NO-2-5"],
                ["炭烧雨林-日", "NO-2-6"],
                ["炭烧雨林-夜", "NO-2-7"],
                ["抹茶庄园-日", "NO-2-8"],
                ["抹茶庄园-夜", "NO-2-9"],
                ["玛奇朵港", "NO-2-10"],
                ["棉花糖天空-日", "NO-2-11"],
                ["棉花糖天空-夜", "NO-2-12"],
                ["果酱部落-日", "NO-2-13"],
                ["果酱部落-夜", "NO-2-14"],
                ["雪顶火山", "NO-2-15"],
                ["火山漫游", "NO-2-16"],
            ],
            "火山遗迹": [
                ["果仁瀑布", "NO-3-1"],
                ["榛子瀑布", "NO-3-2"],
                ["黑提丛林", "NO-3-3"],
                ["蓝莓丛林", "NO-3-4"],
                ["奶昔基地", "NO-3-5"],
                ["圣代基地", "NO-3-6"]
            ],
            "浮空岛": [
                ["茴香竹筏-日", "NO-4-1"],
                ["茴香竹筏-夜", "NO-4-2"],
                ["孜然断桥-日", "NO-4-3"],
                ["孜然断桥-夜", "NO-4-4"],
                ["卤料花园", "NO-4-5"],
                ["月桂天空-日", "NO-4-6"],
                ["月桂天空-夜", "NO-4-7"],
                ["香叶空港-日", "NO-4-8"],
                ["香叶空港-夜", "NO-4-9"],
                ["香料飞船", "NO-4-10"],
                ["花椒浮岛-日", "NO-4-11"],
                ["花椒浮岛-夜", "NO-4-12"],
                ["丁香彩虹-日", "NO-4-13"],
                ["丁香彩虹-夜", "NO-4-14"],
                ["十三香中心岛", "NO-4-15"],
                ["浮空漫游", "NO-4-16"],
            ],
            "海底旋涡": [
                ["金枪鱼洋流", "NO-5-1"],
                ["珊瑚洋流-日", "NO-5-2"],
                ["珊瑚洋流-夜", "NO-5-3"],
                ["北极贝湍流", "NO-5-4"],
                ["海葵洋流-日", "NO-5-5"],
                ["海葵洋流-夜", "NO-5-6"],
                ["天妇罗旋涡", "NO-5-7"]
            ],
            "星际穿越": [
                ["糖球空间站-日", "NO-6-1"],
                ["糖球空间站-夜", "NO-6-2"],
                ["苏打水星-日", "NO-6-3"],
                ["苏打水星-夜", "NO-6-4"],
                ["汉堡王星", "NO-6-5"],
                ["巴旦木星-日", "NO-6-6"],
                ["巴旦木星-夜", "NO-6-7"],
                ["冷萃星环-日", "NO-6-8"],
                ["冷萃星环-夜", "NO-6-9"],
                ["多拿滋星云", "NO-6-10"]
            ],
            "勇士副本": [
                ["洞君", "WA-0-1"],
                ["阿诺", "WA-0-2"],
                ["冰渣队长", "WA-0-3"],
                ["...", "..."],
                ["嗡嗡中尉", "WA-0-12"],
                ["暴躁杰克", "WA-0-13"],
                ["炽热金刚", "WA-0-14"],
                ["酷帅晓明", "WA-0-15"],
                ["闪亮baby", "WA-0-16"],
                ["美队鼠", "WA-0-17"],
                ["钢铁侠鼠", "WA-0-18"],
                ["绿巨人鼠", "WA-0-19"],
                ["蜘蛛侠鼠", "WA-0-20"],
                ["鼠国高铁", "WA-0-21"],
                ["电光水母鼠", "WA-0-22"],
                ["机械鲨鱼鼠", "WA-0-23"],
            ],
            "探险营地": [
                ["戚风营地-日", "EX-1-1"],
                ["戚风营地-夜", "EX-1-2"],
                ["冰啤酒吧-日", "EX-1-3"],
                ["冰啤酒吧-夜", "EX-1-4"],
                ["坚果高台-日", "EX-1-5"],
                ["坚果高台-夜", "EX-1-6"],
            ],
            "沙漠之旅": [
                ["芦荟沙丘-日", "EX-2-1"],
                ["芦荟沙丘-夜", "EX-2-2"],
                ["沙棘绿洲", "EX-2-3"],
                ["仙人掌盆地-日", "EX-2-4"],
                ["仙人掌盆地-夜", "EX-2-5"],
                ["蜥蜴戈壁", "EX-2-6"],
                ["鱼骨沙漠-日", "EX-2-7"],
                ["鱼骨沙漠-夜", "EX-2-8"],
                ["库库尔金字塔", "EX-2-9"],
            ],
            "雪山探险": [
                ["雪宝棒棒冰-日", "EX-3-1"],
                ["雪宝棒棒冰-夜", "EX-3-2"],
                ["冰巨人雪芭-日", "EX-3-3"],
                ["冰巨人雪芭-夜", "EX-3-4"],
                ["爱莎星冰乐", "EX-3-5"],
            ],
            "雷城探险": [
                ["动感街区-日", "EX-4-1"],
                ["动感街区-夜", "EX-4-2"],
                ["蛋糕钟楼-日", "EX-4-3"],
                ["蛋糕钟楼-夜", "EX-4-4"],
                ["莓莓音乐节-日", "EX-4-5"],
                ["莓莓音乐节-夜", "EX-4-6"],
            ],
            "漫游奇境": [
                ["兔子洞-日", "EX-5-1"],
                ["兔子洞-夜", "EX-5-2"],
                ["蘑菇小径-日", "EX-5-3"],
                ["蘑菇小径-夜", "EX-5-4"],
                ["午茶庭院", "EX-5-5"],
                ["玫瑰花园-日", "EX-5-6"],
                ["玫瑰花园-夜", "EX-5-7"],
                ["悬浮梦境", "EX-5-8"],
            ],
            "跨服副本": [
                ["跨服-城堡", "CS-1-? (1-8)"],
                ["跨服-天空", "CS-2-? (1-8)"],
                ["跨服-炼狱", "CS-3-? (1-8)"],
                ["跨服-水火", "CS-4-? (1-8)"],
                ["跨服-巫毒", "CS-5-? (1-8)"],
                ["跨服-冰跨", "CS-6-? (1-8)"],
            ],
            "爬塔": [
                ["魔塔-单人", "MT-1-? (1-165)"],
                ["魔塔-单人爬塔", "MT-1-0"],
                ["魔塔-双人", "MT-2-? (1-100)"],
                ["魔塔-双人爬塔", "MT-2-0"],
                ["魔塔-密室", "MT-3-? (1-4)"],
                ["萌宠神殿", "PT-0-? (1-25)"],
                ["萌宠神殿-爬塔", "PT-0-0"],
            ],
            "多元奇遇（4-7未实装)": [
                ["谷神殿", "MU-1-0"],
                ["星渊岛", "MU-1-1"],
                ["琉璃沙堡", "MU-2-2"],
                ["吉拉朵港", "MU-2-3"],
                ["大火山", "MU-2-4"],
                ["大花园", "MU-4-5"],
                ["大飞船", "MU-4-6"],
                ["大十三香", "MU-4-7"],
            ],
            "其他": [
                ["悬赏关卡", "OR-0-? (1-4)"],
                ["公会副本", "GD-0-? (1-4)"],
                ["生肖副本", "CZ-0-? (1-4)"],
                ["欢乐假期", "HH-0-0"],
                ["巅峰对决-默认", "WB-0-0"],
                ["巅峰对决-煎蛋", "WB-0-1"],
                ["巅峰对决-火盾", "WB-0-2"],
                ["巅峰对决-石盾", "WB-0-3"],
                ["巅峰对决-自定", "WB-0-? (4-100)"],
            ]
        }

        # 设置表头
        table_headers = list(data_dict.keys())

        # 表格初始化
        table.setRowCount(max([len(values) for values in data_dict.values()]) + 1)  # 表高
        table.setColumnCount(len(table_headers) * 2)  # 表宽

        # 列宽
        for column in range(table.columnCount()):
            if column % 2 == 0:  # 判断是否为偶数列
                table.setColumnWidth(column, 100)  # 设置偶数列的宽度
            else:  # 奇数列
                table.setColumnWidth(column, 100)  # 设置奇数列的宽度

        # 设置表头
        for index, header_text in enumerate(table_headers):
            span = 2  # 每个表头默认合并两列
            start_col = index * 2
            table.setSpan(0, start_col, 1, span)
            table.setItem(0, start_col, QTableWidgetItem(header_text))

        # 填充表格内容
        row = 1
        for col_index, header in enumerate(table_headers):
            for item1, item2 in data_dict[header]:
                table.setItem(row, col_index * 2, QTableWidgetItem(item1))
                table.setItem(row, col_index * 2 + 1, QTableWidgetItem(item2))
                row += 1
            row = 1  # 重置行号以填充下一个表头的内容

        def is_in_sequence(x):
            # 计算 k1 和 k2
            k1 = (x - 2) / 4
            k2 = (x - 3) / 4

            # 检查 k1 或 k2 是否为非负整数
            if k1.is_integer() and k1 >= 0:
                return True
            if k2.is_integer() and k2 >= 0:
                return True

            return False

        # 上透明色
        for column in range(table.columnCount()):
            if is_in_sequence(column):
                for row in range(table.rowCount()):
                    item = table.item(row, column)
                    if item:
                        item.setBackground(QColor(255, 255, 0, 50))
        # 设置布局
        layout = QVBoxLayout()
        layout.addWidget(table)

        # 设置主控件
        main_widget = QWidget()
        main_widget.setLayout(layout)

        # 将 控件注册 为 窗口主控件
        self.setCentralWidget(main_widget)
