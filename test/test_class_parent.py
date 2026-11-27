class FAAActionInterfaceJump:
    def __init__(self, faa):
        self.faa = faa

    def get_faa_value(self):
        value = self.faa.value
        return value


class FAA:
    def __init__(self):
        self.value = 0
        self.action_jump = FAAActionInterfaceJump(self)

    def set_value(self, new_value):
        self.value = new_value

    def print_action_jump_value(self):
        print(self.action_jump.get_faa_value())


def test_faa_parameter_change():
    # 创建 FAA 实例
    faa = FAA()

    # 修改 FAA 实例的值
    faa.set_value(10)

    # 检查 FAAActionInterfaceJump 中的 faa 参数是否发生变化
    faa.print_action_jump_value()


# 运行测试
test_faa_parameter_change()
