## 运行主函数并生成 文件 保存运行性能信息

python -m cProfile -o "D:\Project_Python\WorkSpace\FoodsVsMouses_AutoAssistant\function\performance_testing.prof" "D:\Project_Python\WorkSpace\FoodsVsMouses_AutoAssistant\function\main.py"

# 可视化

pip install snakeviz

snakeviz "D:\Project_Python\WorkSpace\FoodsVsMouses_AutoAssistant\function\performance_testing.prof" 