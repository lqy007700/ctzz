#!/bin/bash

# 杀掉关键字为 trade.py 的进程
pkill -f trade.py

# 执行 nohup python3 trade.py，并将输出重定向到 /dev/null
nohup python3 trade.py > /dev/null 2>&1 &