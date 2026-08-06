#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import random
import sys
from urllib.parse import urlencode, quote

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
    # 优先使用完整 user_account（含后缀），兼容旧版仅保存 username 的状态
    user_account = state.get("user_account", "")
    if not user_account and username:
        # 旧版状态：尝试从 config.env 读取 suffix 拼接
        from dotenv import dotenv_values as _dv
        _cfg = _dv(os.path.join(CONFIG_DIR, "config.env"))
        suffix = _cfg.get("SUFFIX", "")
        user_account = f",0,{username}{suffix}"
    wlan_user_mac = state.get("wlan_user_mac", "")
    wlan_user_ip = state.get("wlan_user_ip", "")

    if not all([host, user_account, wlan_user_mac, wlan_user_ip]):
        print("❌ 登录状态文件参数不完整。")
        return EXIT_NO_STATE

    v = str(random.randint(1000, 9999))
    params = {
        "callback": "dr1002",
        "user_account": user_account,
        "wlan_user_mac": wlan_user_mac,
        "wlan_user_ip": wlan_user_ip,
        "jsVersion": "4.2",
        "v": v,
        "lang": "en",
    }
    query = urlencode(params, quote_via=quote)
    url = f"http://{host}:801/eportal/portal/mac/unbind?{query}"

    if DEBUG:
        print(f"[DEBUG] 登出 URL: {url}")

    print(f"正在登出... (host={host}, account={user_account})")
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
