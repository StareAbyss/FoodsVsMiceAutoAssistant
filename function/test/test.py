num_mat_card = 3
my_list = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]
other_list = []
for i in range(num_mat_card):
    other_list.append(my_list[i::num_mat_card])
print(other_list)