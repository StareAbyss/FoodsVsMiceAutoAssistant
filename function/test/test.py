my_str = "NO-1-7_呜呜呜呜-1.png"
task_card = "None"

# 去.png
my_str = my_str.split(".")[0]

num_of_line = my_str.count("_")

if num_of_line == 0:
    stage = my_str
else:
    my_list = my_str.split("_")
    stage = my_list[0]

    if num_of_line == 1:
        if not my_list[1].isdigit():
            task_card = my_list[1]
    elif num_of_line == 2:
        task_card = my_list[2]

print(stage)
print(task_card)
