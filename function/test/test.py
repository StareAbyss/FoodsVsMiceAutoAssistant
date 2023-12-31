import datetime
import time
start_time = datetime.datetime.now()
time.sleep(1)

delta = datetime.datetime.now() - start_time
print(delta)
print(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(delta.seconds)))