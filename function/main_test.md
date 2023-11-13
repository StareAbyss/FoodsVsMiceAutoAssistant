## 运行主函数并生成 文件 保存运行性能信息

python -m cProfile -o "D:\Project_Python\WorkSpace\FoodsVsMouses_AutoAssistant\function\performance_testing.prof" "D:\Project_Python\WorkSpace\FoodsVsMouses_AutoAssistant\function\main.py"

# 可视化

pip install graphviz
pip install gprof2dot

gprof2dot -f pstats "D:\Project_Python\WorkSpace\FoodsVsMouses_AutoAssistant\function\performance_testing.prof" | -Tpng -o "D:\Project_Python\WorkSpace\FoodsVsMouses_AutoAssistant\function\performance_testing.png"
