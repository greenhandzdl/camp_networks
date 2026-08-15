#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dr.COM 校园网登出 CLI（模块场景入口）
薄封装：读取状态 → 调 drcom_core.perform_logout → 按 CLI 格式打印
"""

import os
import sys

from drcom_core import (
    LoginState, perform_logout,
    EXIT_SUCCESS, EXIT_NETWORK_ERROR, EXIT_LOGIN_FAILED,
)

# ---------- 状态文件路径 ----------
CONFIG_DIR = os.environ.get("DRCOM_CONFIG_DIR", "/data/adb/modules/drcom-wlan-login")
STATE_PATH = os.path.join(CONFIG_DIR, "login_state.json")

# ---------- 返回码 ----------
EXIT_NO_STATE = 1


def main():
    DEBUG = os.environ.get("DEBUG", "false").lower() in ("true", "1", "yes")

    if not os.path.exists(STATE_PATH):
        print("❌ 未找到登录状态文件 login_state.json，可能尚未登录。")
        return EXIT_NO_STATE

    state = LoginState.load(STATE_PATH)
    if not state or not all([state.host, state.username, state.mac, state.ip]):
        print("❌ 登录状态文件参数不完整。")
        return EXIT_NO_STATE

    if DEBUG:
        from drcom_core import build_logout_url
        url = build_logout_url(state.host, state.username, state.mac, state.ip)
        print(f"[DEBUG] 登出 URL: {url}")

    print(f"正在登出... (host={state.host}, account={state.username})")
    ok, response = perform_logout(state.host, state.username, state.mac, state.ip)
    if not ok:
        print(f"❌ 登出请求失败: {response}")
        return EXIT_LOGIN_FAILED

    print(f"📄 登出响应: {response}")
    if "result" in response.lower():
        print("✅ 登出请求已发送。")
    else:
        print("⚠️ 响应内容异常，但请求已完成。")
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
