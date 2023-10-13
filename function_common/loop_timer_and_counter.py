from time import sleep, time


def loop_timer_and_counter(count_max, f_function, *args):
    time_flag = time()
    if len(args) > 0:
        args = args[0]
    for count in range(count_max):
        print("第 {:.0f} 次开始...".format(count + 1))
        f_function(args)
        print("第 {:.0f} 次完成,耗时{:.3f}s".format(count + 1, time() - time_flag))
        time_flag = time()


if __name__ == '__main__':
    def wa(list_input):
        i = list_input[0]
        j = list_input[1]
        k = list_input[2]
        o = list_input[3]
        print(i, j, k, o)
        sleep(1)


    loop_timer_and_counter(10, wa, [10, 11, 12, 13])
