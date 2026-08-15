#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dr.COM 校园网认证 CLI（模块场景入口）
薄封装：读取 config.env → 构造 DrComConfig → 调 drcom_core.login_flow → 按 CLI 格式打印
"""

import os
import sys

from dotenv import dotenv_values

from drcom_core import (
    DrComConfig, EXIT_SUCCESS, EXIT_NETWORK_ERROR, EXIT_PARSE_ERROR,
    check_internet, check_gateway, fetch_gateway_params,
    perform_login, parse_login_response,
    EXIT_LOGIN_FAILED, EXIT_AUTH_ERROR, EXIT_UNKNOWN,
)

# ---------- 配置读取 ----------
CONFIG_DIR = os.environ.get("DRCOM_CONFIG_DIR", "/data/adb/modules/drcom-wlan-login")
ENV_PATH = os.path.join(CONFIG_DIR, "config.env")
STATE_PATH = os.path.join(CONFIG_DIR, "login_state.json")

if not os.path.exists(ENV_PATH):
    print("❌ 配置文件 config.env 不存在，请先通过 WebUI 保存设置。")
    sys.exit(1)

_cfg = dotenv_values(ENV_PATH)
CONFIG = DrComConfig(
    username=_cfg.get("USERNAME", ""),
    password=_cfg.get("PASSWORD", ""),
    suffix=_cfg.get("SUFFIX", "@cmcc"),
    auth_server=_cfg.get("AUTH_SERVER", "10.0.1.5"),
    redirect_server=_cfg.get("REDIRECT_SERVER", "1.2.3.4"),
    ipv6=_cfg.get("IPV6_ADDRESS", ""),
    debug=_cfg.get("DEBUG", "false").lower() in ("true", "1", "yes"),
)


def log_debug(msg):
    if CONFIG.debug:
        print(f"[DEBUG] {msg}")


# ---------- 主流程（保持与旧版一致的输出格式）----------
def main():
    print("🔍 正在检测网络状态...")
    if check_internet(CONFIG):
        print("✅ 外网已连通，无需认证。")
        return EXIT_SUCCESS

    log_debug(f"检测网关: GET http://{CONFIG.redirect_server}")
    if not check_gateway(CONFIG):
        print(f"❌ 网关 {CONFIG.redirect_server} 不可达，网络异常。")
        return EXIT_NETWORK_ERROR

    print("✅ 网关可达，开始获取认证参数...")
    params = fetch_gateway_params(CONFIG)
    if any(p is None for p in params):
        print("❌ 获取网关参数失败。")
        return EXIT_PARSE_ERROR

    host, wlan_user_ip, wlan_ac_name, wlan_ac_ip, wlan_user_mac = params
    log_debug(f"host={host} ip={wlan_user_ip} ac={wlan_ac_name} ac_ip={wlan_ac_ip} mac={wlan_user_mac}")
    print("✅ 获取参数成功，执行登录...")

    ok, response = perform_login(CONFIG, host, wlan_user_ip, wlan_ac_name,
                                 wlan_ac_ip, wlan_user_mac)
    if not ok:
        print(f"❌ 登录请求失败: {response}")
        return EXIT_LOGIN_FAILED

    print("📄 登录响应：", response)
    ok_parse, msg = parse_login_response(response)
    if not ok_parse:
        print("⚠️ 未知响应，可能失败。")
        return EXIT_AUTH_ERROR
    print("✅ 认证成功，等待生效...")

    # 保存登录状态供登出使用
    from drcom_core import LoginState
    state = LoginState(host=host, username=CONFIG.username,
                       mac=wlan_user_mac, ip=wlan_user_ip)
    if state.save(STATE_PATH):
        log_debug(f"登录状态已保存到 {STATE_PATH}")

    import time
    time.sleep(3)
    if check_internet(CONFIG):
        print("🎉 登录成功！外网已连通。")
        return EXIT_SUCCESS
    print("⚠️ 外网仍未连通，请检查。")
    return EXIT_UNKNOWN


if __name__ == "__main__":
    sys.exit(main())
