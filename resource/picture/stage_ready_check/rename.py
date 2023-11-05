import os

my_list = os.listdir("\\")
print(my_list)
for i in my_list:
    if i.find("]") == -1:
        continue
    else:
        os.rename(i, i.split("]")[0][1:] + ".png")
        print(i.split("]")[0][1:] + ".png")
