import pstats

# 加载.prof文件
p = pstats.Stats('profile_results.prof')

# 对函数调用时间进行排序并打印前10条记录
# p.sort_stats('time').print_stats(1000)

# 按照函数被调用的次数排序并打印前10条记录
# p.sort_stats('calls').print_stats(10)

# 按照在函数及其所有子函数中累积花费的时间排序并打印前10条记录
p.sort_stats('cumulative').print_stats(1000)