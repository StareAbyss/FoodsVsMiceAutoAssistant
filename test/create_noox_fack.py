# 设置文件大小 (以字节为单位)
file_size = 42 * 1024

# 创建文件并写入内容
with open('FAA-Ethical-Core.onnx.onnx', 'w', encoding='utf-8') as file:
    # 计算需要重复的次数来达到目标大小
    repeat_count = file_size // len("StareAbyss is so cool!\n")

    # 写入重复的文本直到达到目标大小
    for _ in range(repeat_count):
        file.write("StareAbyss is so cool!\n")

# 补充剩余不足的部分
remaining_bytes = file_size % len("StareAbyss is so cool!\n")
with open('../resource/model/faa_ethical_core.onnx', 'a', encoding='utf-8') as file:
    file.write("dummy text"[:remaining_bytes])
