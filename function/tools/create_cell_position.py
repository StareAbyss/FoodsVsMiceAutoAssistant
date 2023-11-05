import re

cell_x = 332
cell_y = 143
cell_x_add = 60.11
cell_y_add = 63.71
cell_dict = {}
cell_str = ""
for i in range(9):  # x9列 y7行  用行-列寻找对应值
    for j in range(7):
        x = int(cell_x + i * cell_x_add)
        y = int(cell_y + j * cell_y_add)
        cell_dict.update({"{}-{}".format(str(i + 1), str(j + 1)): [x, y]})
        cell_str += "'{}-{}': [{}, {}]".format(i + 1, j + 1, x, y)
print(cell_str)
b = re.findall(r"..., ...", cell_str)
c = re.findall(r".-.", cell_str)
return_str = ""
for i in range(len(b)):
    w = "int({} * dpi), int({} * dpi)".format(b[i].split(", ")[0], b[i].split(", ")[1])
    return_str = return_str + "'" + c[i] + "': [" + w + "],"

print(return_str)
