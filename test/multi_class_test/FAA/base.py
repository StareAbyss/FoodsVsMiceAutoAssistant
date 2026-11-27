from test.multi_class_test.FAA.protocol import FAAProtocol


class FAABase:
    def __init__(self:FAAProtocol):
        self.common_property = "基类属性"

    def base_method(self:FAAProtocol):
        print("基类方法")
