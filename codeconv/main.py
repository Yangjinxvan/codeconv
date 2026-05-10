import time
import random
import os
import sys

version = sys.version_info

print("检查网络中……")
time.sleep(random.random())
if os.name == 'nt':
    command = "ping 8.8.8.8 -n 1 -w 1000 >nul 2>&1"
else:
    command = "ping 8.8.8.8 -c 1 -W 1 >/dev/null 2>&1"

if os.system(command) != 0:
    print("进入失败！请先连接上网络！")
    sys.exit()

print("网络已连接！正在进入中……")
time.sleep(random.uniform(2.0, 4.0))

if version >= (3, 10):
    exec(open(os.path.join('.', 'src', 'codeconv.py'), mode='r', encoding='utf-8', errors='ignore').read())
else:
    print("进入失败！请先升级Pyton版本到3.10及以上！")