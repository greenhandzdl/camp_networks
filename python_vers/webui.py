#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import subprocess
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

# ---------- 路径配置 ----------
CONFIG_DIR = os.environ.get("DRCOM_CONFIG_DIR", "/data/adb/modules/drcom-wlan-login")
ENV_PATH = os.path.join(CONFIG_DIR, "config.env")

# webui.py 与 wlan_login.py 在同一目录（python_vers）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPT_PATH = os.path.join(SCRIPT_DIR, "wlan_login.py")

PORT = 38080

class WebUIHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            config = self._read_env()
            html = self._generate_form(config)
            self.wfile.write(html.encode("utf-8"))
        elif parsed.path == "/run":
            self._run_script()
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/save":
            content_len = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_len).decode()
            params = parse_qs(post_data)
            username = params.get('username', [''])[0].strip()
            password = params.get('password', [''])[0].strip()
            suffix = params.get('suffix', [''])[0].strip()
            debug = params.get('debug', ['false'])[0].strip().lower() in ('true', '1')
            env_content = f"""USERNAME={username}
PASSWORD={password}
ACCOUNT_SUFFIX={suffix}
DEBUG={str(debug).lower()}
"""
            # 确保配置目录存在（模块根目录）
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(ENV_PATH, 'w') as f:
                f.write(env_content)
            self.send_response(302)
            self.send_header('Location', '/')
            self.end_headers()
        else:
            self.send_error(404)

    def _read_env(self):
        config = {
            'username': '',
            'password': '',
            'suffix': '@cmcc',
            'debug': 'false'
        }
        if os.path.exists(ENV_PATH):
            with open(ENV_PATH, 'r') as f:
                for line in f:
                    line = line.strip()
                    if '=' in line and not line.startswith('#'):
                        k, v = line.split('=', 1)
                        config[k.lower()] = v
        return config

    def _generate_form(self, config):
        return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Dr.COM 认证配置</title></head>
<body>
<h2>Wi-Fi 认证设置</h2>
<form method="POST" action="/save">
  <label>账号：<input type="text" name="username" value="{config.get('username','')}"></label><br>
  <label>密码：<input type="password" name="password" value="{config.get('password','')}"></label><br>
  <label>后缀：<input type="text" name="suffix" value="{config.get('suffix','@cmcc')}"></label><br>
  <label>调试模式：<input type="checkbox" name="debug" value="true" {'checked' if config.get('debug')=='true' else ''}></label><br>
  <input type="submit" value="保存配置">
</form>
<hr>
<form action="/run" method="GET">
  <input type="submit" value="立即运行认证脚本">
</form>
<div id="result"></div>
<script>
document.querySelector('form[action="/run"]').addEventListener('submit', function(e) {{
    e.preventDefault();
    fetch('/run')
      .then(r => r.text())
      .then(data => {{
        document.getElementById('result').innerHTML = '<pre>' + data + '</pre>';
      }});
}});
</script>
</body>
</html>"""

    def _run_script(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        try:
            result = subprocess.run(
                [sys.executable, SCRIPT_PATH],
                capture_output=True,
                text=True,
                timeout=60
            )
            output = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        except Exception as e:
            output = f"执行失败: {e}"
        self.wfile.write(output.encode('utf-8'))

def main():
    server = HTTPServer(('0.0.0.0', PORT), WebUIHandler)
    print(f"WebUI 已启动，请访问 http://本机IP:{PORT}")
    print("按 Ctrl+C 停止")
    server.serve_forever()

if __name__ == "__main__":
    main()