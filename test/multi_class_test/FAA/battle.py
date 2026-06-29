from test.multi_class_test.FAA.protocol import FAAProtocol


class BattleMixin:
    def battle_method(self:FAAProtocol):
        print("战斗模块方法 -> 访问工具模块方法")
        self.utils_method()
        print(self.common_property)
