quest_list = [{1:1,2:2},{3:3,4:4}]
quest = {1:1,2:2}
if quest in quest_list:
    quest_list.remove(quest)

print(quest_list)