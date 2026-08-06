#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import random
import sys

import requests
from dotenv import load_dotenv

# ---------- 配置文件路径 ----------
CONFIG_DIR = os.environ.get("DRCOM_CONFIG_DIR", "/data/adb/modules/drcom-wlan-login")
STATE_PATH = os.path.join(CONFIG_DIR, "login_state.json")

# ---------- 返回码 ----------
EXIT_SUCCESS = 0
EXIT_NO_STATE = 1
EXIT_NETWORK_ERROR = 2
EXIT_LOGOUT_FAILED = 3


def main():
    load_dotenv(os.path.join(CONFIG_DIR, "config.env"))
    DEBUG = os.environ.get("DEBUG", "false").lower() in ("true", "1", "yes")

    if not os.path.exists(STATE_PATH):
        print("❌ 未找到登录状态文件 login_state.json，可能尚未登录。")
        return EXIT_NO_STATE

    try:
        with open(STATE_PATH, "r") as f:
            state = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"❌ 读取登录状态文件失败: {e}")
        return EXIT_NO_STATE

    host = state.get("host", "")
    username = state.get("username", "")
    wlan_user_mac = state.get("wlan_user_mac", "")
    wlan_user_ip = state.get("wlan_user_ip", "")

    if not all([host, username, wlan_user_mac, wlan_user_ip]):
        print("❌ 登录状态文件参数不完整。")
        return EXIT_NO_STATE

    v = str(random.randint(1000, 9999))
    url = (
        f"http://{host}:801/eportal/portal/mac/unbind"
        f"?callback=dr1002"
        f"&user_account={username}"
        f"&wlan_user_mac={wlan_user_mac}"
        f"&wlan_user_ip={wlan_user_ip}"
        f"&jsVersion=4.2"
        f"&v={v}"
        f"&lang=en"
    )

    if DEBUG:
        print(f"[DEBUG] 登出 URL: {url}")

    print(f"正在登出... (host={host}, user={username})")
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        print(f"📄 登出响应: {resp.text}")
        if "result" in resp.text.lower():
            print("✅ 登出请求已发送。")
            return EXIT_SUCCESS
        else:
            print("⚠️ 响应内容异常，但请求已完成。")
            return EXIT_SUCCESS
    except requests.RequestException as e:
        print(f"❌ 登出请求失败: {e}")
        return EXIT_LOGOUT_FAILED


if __name__ == "__main__":
    sys.exit(main())
