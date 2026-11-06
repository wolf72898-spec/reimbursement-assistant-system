#!/bin/sh
# 云端沙箱启动入口：PORT 由平台注入，本地缺省 3000
PORT_NUM="${PORT:-3000}"
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT_NUM"
