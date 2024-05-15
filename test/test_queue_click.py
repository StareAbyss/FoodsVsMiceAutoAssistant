from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER
from function.scattered.gat_handle import faa_get_handle

handle = faa_get_handle(channel="锑食-微端", mode="flash")

T_ACTION_QUEUE_TIMER.set_zoom_rate(1.0)

for i in range(1000):
    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=1, y=1)



