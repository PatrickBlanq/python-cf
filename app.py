#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from http.server import BaseHTTPRequestHandler, HTTPServer
import socket

# =========================
# 自动获取翼龙分配端口
# =========================
PORT = int(
    os.environ.get("SERVER_PORT", 8080)
)

# =========================
# 获取服务器 IP
# =========================
def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "0.0.0.0"

IP = get_ip()

# =========================
# Web 页面
# =========================
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()

        html = f"""
        <html>
        <head>
            <title>Hello World</title>
        </head>
        <body style="background:#111;color:#0f0;font-family:monospace;">
            <h1>Hello World 🚀</h1>
            <p>翼龙面板 Python 服务已运行</p>
            <p>IP: {IP}</p>
            <p>PORT: {PORT}</p>
        </body>
        </html>
        """

        self.wfile.write(html.encode("utf-8"))

# =========================
# 启动服务
# =========================
server = HTTPServer(("0.0.0.0", PORT), Handler)

print("=" * 50)
print("Hello World Server Started")
print(f"Listening: http://{IP}:{PORT}")
print("=" * 50)

server.serve_forever()
