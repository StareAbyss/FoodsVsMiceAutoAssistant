import os

my_list = os.listdir("\\")
print(my_list)
for i in my_list:
    if i.find(".") == -1:
        os.rename(i, i + ".png")
        print(i + ".png")
    else:
        continue

