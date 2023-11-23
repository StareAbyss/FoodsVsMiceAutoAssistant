import cProfile


class MyClass:
    def __init__(self, variable):
        self.variable = variable

    def my_function_0(self):
        variable_sum = 0.0
        for i in range(10000000):
            self.variable
        print(variable_sum)

    def my_function_1(self):
        variable_sum = 0.0
        variable = self.variable
        for i in range(10000000):
            variable
        print(variable_sum)

    def my_function_2(self):
        variable_sum = 0.0
        for i in range(10000000):
            variable = 1.0
        print(variable_sum)


if __name__ == '__main__':
    """
    结论
    如果需要多次调用类中的variable, 
    直接调用最慢
    给个变量 - 36% 耗时
    给个变量,但变量名短 - 无影响
    读取类变量(100%) < 创建变量(79.0%) < 调用变量(63.5%)
    """
    my_class = MyClass(1.0)
    cProfile.run('my_class.my_function_0()')
    cProfile.run('my_class.my_function_1()')
    cProfile.run('my_class.my_function_2()')
