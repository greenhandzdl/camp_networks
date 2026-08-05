#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dr.COM WLAN 认证 WebUI 主程序：HTTP Handler + 路由 + 服务启动"""

import json
import os
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs

from webui_utils.constants import (
    DEFAULT_PORT, DEFAULT_SUFFIX, DEFAULT_LOG_FILE, DEFAULT_DOWNLOAD_DIR,
    DEFAULT_AUTO_INTERVAL, DEFAULT_AUTO_DELAY,
    LOG_TAIL_LINES, SHUTDOWN_DELAY,
)
from webui_utils.config import read_env, write_env, read_port, read_module_prop
from webui_utils.network import get_wifi_info, get_ip_addresses
from webui_utils.auth import exec_login, stop_login, get_run_status, auto_loop, _auto_state
from webui_utils.update import check_update_all, download_update
from webui_utils.html import HTML_PAGE

_server = None


class WebUIHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _post_params(self):
        length = int(self.headers.get("Content-Length", 0))
        return parse_qs(self.rfile.read(length).decode())

    def _param(self, params, key, default=""):
        return params.get(key, [default])[0].strip()

    # ---------- 路由 ----------
    _GET_ROUTES = {
        "/":              "_serve_html",
        "/api/config":    "_api_config",
        "/api/prop":      "_api_prop",
        "/api/run":       "_api_run",
        "/api/run_status": "_api_run_status",
        "/api/network":   "_api_network",
        "/api/log":       "_api_log",
        "/api/check_update": "_api_check_update",
    }
    _POST_ROUTES = {
        "/api/save":         "_api_save",
        "/api/save_auto":    "_api_save_auto",
        "/api/save_service": "_api_save_service",
        "/api/stop_run":     "_api_stop_run",
        "/api/do_update":    "_api_do_update",
    }

    def do_GET(self):
        path = self.path.split("?")[0]
        handler = self._GET_ROUTES.get(path)
        if handler:
            getattr(self, handler)()
        else:
            self.send_error(404)

    def do_POST(self):
        handler = self._POST_ROUTES.get(self.path.split("?")[0])
        if handler:
            getattr(self, handler)()
        else:
            self.send_error(404)

    # ---------- GET 处理 ----------
    def _serve_html(self):
        html = (HTML_PAGE.replace("__SUFFIX__", DEFAULT_SUFFIX)
                .replace("__PORT__", str(DEFAULT_PORT))
                .replace("__LOGFILE__", DEFAULT_LOG_FILE)
                .replace("__DOWNLOAD__", DEFAULT_DOWNLOAD_DIR)
                .replace("__INTERVAL__", str(DEFAULT_AUTO_INTERVAL))
                .replace("__DELAY__", str(DEFAULT_AUTO_DELAY)))
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def _api_config(self):
        self._json(read_env())

    def _api_prop(self):
        self._json(read_module_prop())

    def _api_run(self):
        r = exec_login()
        if r is None:
            return self._json({"ok": False, "error": "busy", "output": "已有认证任务正在运行"})
        self._json({"ok": r[0], "output": r[1]})

    def _api_run_status(self):
        self._json(get_run_status())

    def _api_stop_run(self):
        stopped = stop_login()
        self._json({"ok": stopped, "error": "" if stopped else "无正在运行的任务"})

    def _api_network(self):
        self._json({**get_wifi_info(), **get_ip_addresses()})

    def _api_log(self):
        path = read_env().get("log_file", DEFAULT_LOG_FILE)
        try:
            with open(path, "r", errors="replace") as f:
                content = "".join(f.readlines()[-LOG_TAIL_LINES:])
        except OSError as e:
            content = f"无法读取日志: {e}"
        self._json({"path": path, "content": content})

    def _api_check_update(self):
        prop = read_module_prop()
        ver = prop.get("version", "unknown")
        try:
            cur_code = int(prop.get("versionCode", 0))
        except ValueError:
            cur_code = 0
        sources, best, err = check_update_all()
        if err:
            return self._json({"error": err, "current_version": ver})
        for s in sources:
            if s.get("ok"):
                s["is_newer"] = s["versionCode"] > cur_code
        self._json({
            "sources": sources, "best": best,
            "current_version": ver,
            "has_update": best["versionCode"] > cur_code if best else False,
        })

    def _api_do_update(self):
        try:
            p = self._post_params()
            source_name = self._param(p, "source", "")
            sources, best, err = check_update_all()
            if err:
                return self._json({"ok": False, "error": err, "output": ""})
            selected = None
            if source_name:
                selected = next((s for s in sources if s["name"] == source_name and s.get("ok")), None)
            if not selected:
                selected = best
            if not selected:
                return self._json({"ok": False, "error": "无可用更新源", "output": ""})

            dl_dir = read_env().get("download_dir", DEFAULT_DOWNLOAD_DIR) or DEFAULT_DOWNLOAD_DIR
            ok, output, _ = download_update(selected, dl_dir)
            self._json({"ok": ok, "error": "" if ok else output, "output": output if ok else ""})
        except Exception as e:
            self._json({"ok": False, "error": str(e), "output": ""})

    # ---------- POST 处理 ----------
    def _api_save(self):
        p = self._post_params()
        debug = self._param(p, "debug", "false").lower() in ("true", "1")
        write_env(
            username=self._param(p, "username"),
            password=self._param(p, "password"),
            suffix=self._param(p, "suffix", DEFAULT_SUFFIX),
            debug=str(debug).lower(),
        )
        self._json({"ok": True})

    def _api_save_auto(self):
        p = self._post_params()
        auto_run = self._param(p, "auto_run", "false").lower() in ("true", "1")
        try:
            interval = int(self._param(p, "auto_interval", str(DEFAULT_AUTO_INTERVAL)))
            if interval < 1:
                raise ValueError
        except ValueError:
            return self._json({"ok": False, "error": "间隔需为不小于 1 的整数（分钟）"})
        try:
            delay = int(self._param(p, "auto_delay", str(DEFAULT_AUTO_DELAY)))
            if delay < 0:
                raise ValueError
        except ValueError:
            return self._json({"ok": False, "error": "延迟需为非负整数（秒）"})
        write_env(auto_run=str(auto_run).lower(),
                  target_essid=self._param(p, "target_essid"),
                  auto_interval=str(interval),
                  auto_delay=str(delay))
        # 保存后重置调度：如已接入目标 WiFi 则重新按 delay 安排
        if _auto_state["connected"]:
            _auto_state["next_run"] = time.time() + delay
        self._json({"ok": True})

    def _api_save_service(self):
        p = self._post_params()
        try:
            port = int(self._param(p, "port"))
            if not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            return self._json({"ok": False, "error": "端口范围 1-65535"})
        log_file = self._param(p, "log_file", DEFAULT_LOG_FILE)
        download_dir = self._param(p, "download_dir", DEFAULT_DOWNLOAD_DIR)
        port_changed = port != read_port()
        write_env(port=str(port), log_file=log_file, download_dir=download_dir)
        self._json({"ok": True, "port_changed": port_changed})
        if port_changed:
            threading.Timer(SHUTDOWN_DELAY, _shutdown).start()


def _shutdown():
    global _server
    print("端口已更改，WebUI 正在关闭...")
    if _server:
        _server.shutdown()
    os._exit(0)


def main():
    global _server
    threading.Thread(target=auto_loop, daemon=True).start()
    port = read_port()
    _server = HTTPServer(("0.0.0.0", port), WebUIHandler)
    print(f"WebUI 已启动，请访问 http://127.0.0.1:{port}")
    print("按 Ctrl+C 停止")
    _server.serve_forever()


if __name__ == "__main__":
    main()
