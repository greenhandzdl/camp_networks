#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dr.COM 有线网络认证脚本（直接使用 /drcom/login 接口）
适用于：已获得 IP（v4/v6），只需通过认证开通外网的环境。
"""

import os
import sys
import time
import random
import socket
import base64
import re
import json
from urllib.parse import urlencode, quote

import requests
from dotenv import load_dotenv

# ---------- 加载环境变量 ----------
load_dotenv()

USERNAME = os.getenv("USERNAME", "")          # 如 "your_username"
PASSWORD = os.getenv("PASSWORD", "")          # 如 "your_password"
ACCOUNT_SUFFIX = os.getenv("ACCOUNT_SUFFIX", "@cmcc")   # 后缀，如 @cmcc
DEBUG = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
# 认证服务器地址（通常固定，也可通过环境变量覆盖）
AUTH_SERVER = os.getenv("AUTH_SERVER", "10.0.1.5")

# ---------- 返回码定义 ----------
EXIT_SUCCESS = 0          # 成功（已在线或登录成功）
EXIT_NETWORK_ERROR = 1    # 外网不可达且网关不可达（网络异常）
EXIT_LOGIN_FAILED = 3     # 登录请求失败（网络错误或服务器无响应）
EXIT_AUTH_ERROR = 4       # 认证失败（账号密码错误或参数不匹配）
EXIT_UNKNOWN = 5          # 登录后外网仍未连通（可能未生效，需人工检查）

# ---------- 辅助函数 ----------
def log_debug(msg):
    if DEBUG:
        print(f"[DEBUG] {msg}")

def get_local_ipv4():
    """获取本机出口 IPv4 地址（非 127.0.0.1）"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        # 备选：从网卡获取（需安装 netifaces，可选）
        try:
            import netifaces
            for iface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(iface)
                if netifaces.AF_INET in addrs:
                    for addr in addrs[netifaces.AF_INET]:
                        ip = addr['addr']
                        if ip != '127.0.0.1' and not ip.startswith('169.254'):
                            return ip
        except ImportError:
            pass
        # 最后尝试通过 hostname 获取
        try:
            return socket.gethostbyname(socket.gethostname())
        except:
            return "0.0.0.0"

def get_local_ipv6():
    """获取本机全局 IPv6 地址（非链路本地、回环）"""
    try:
        sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        sock.connect(("2001:4860:4860::8888", 80))
        ipv6 = sock.getsockname()[0]
        sock.close()
        # 过滤掉 fe80::、::1、:: 等无效地址
        if ipv6.startswith("fe80:") or ipv6 == "::1" or ipv6.startswith("::"):
            return ""
        return ipv6
    except Exception:
        return ""

def is_internet_connected():
    """检测是否真正连通外网（百度首页）"""
    url = "http://baidu.com"
    log_debug(f"检测外网: GET {url}")
    try:
        resp = requests.get(url, timeout=5, allow_redirects=True)
        if resp.status_code != 200:
            log_debug(f"状态码: {resp.status_code}，非200")
            return False
        text = resp.text
        if "百度" in text or "baidu" in text.lower():
            # 确保不是认证网关的劫持页面
            if "WISPAccessGateway" not in text:
                return True
        log_debug("响应内容不含百度标志或仍为网关页面")
        return False
    except requests.RequestException as e:
        log_debug(f"请求异常: {e}")
        return False

def is_gateway_reachable():
    """检测默认网关（1.2.3.4）是否在线（仅用于网络状态判断）"""
    url = "http://1.2.3.4"
    log_debug(f"检测网关: GET {url}")
    try:
        resp = requests.get(url, timeout=3, allow_redirects=False)
        if resp.status_code in (200, 301, 302, 303, 307):
            return True
        return False
    except:
        return False

# ---------- 核心认证函数 ----------
def perform_login(username, password):
    """
    通过 /drcom/login 接口进行有线认证
    返回 (success, response_text)
    """
    # 动态获取本机 IP
    ipv4 = get_local_ipv4()
    ipv6 = get_local_ipv6()
    if not ipv6:
        ipv6 = ""  # 若无 IPv6，留空（参数会被忽略）

    log_debug(f"本机 IPv4: {ipv4}, IPv6: {ipv6}")

    # 构造请求参数（参考你提供的 URL）
    params = {
        "callback": "dr1004",
        "DDDDD": username,                 # 如 "your_username@cmcc"
        "upass": password,                 # 明文密码
        "0MKKey": "123456",                # 固定值
        "R1": "0",
        "R2": "",                          # 空值会被忽略
        "R3": "0",
        "R6": "0",
        "para": "00",
        "v4ip": ipv4,
        "v6ip": ipv6,
        "terminal_type": "1",              # 1 = PC
        "lang": "en",
        "jsVersion": "4.2",
        "v": str(int(time.time() * 1000)), # 时间戳（毫秒）
    }
    # 移除空值参数
    params = {k: v for k, v in params.items() if v != ""}

    login_url = f"http://{AUTH_SERVER}/drcom/login"
    query_string = urlencode(params, quote_via=quote)
    full_url = f"{login_url}?{query_string}"

    if DEBUG:
        log_debug(f"完整请求 URL: {full_url}")

    try:
        resp = requests.get(full_url, timeout=5)
        resp.raise_for_status()
        return True, resp.text
    except requests.RequestException as e:
        log_debug(f"登录请求异常: {e}")
        return False, str(e)

# ---------- 主函数 ----------
def main():
    log_debug("===== 有线认证脚本启动 =====")
    print("🔍 正在检测网络连接状态...")

    # 1. 检查外网是否已通
    if is_internet_connected():
        print("✅ 外网已连通，无需认证。")
        return EXIT_SUCCESS

    print("❌ 外网不可达，可能未登录。")

    # 2. 检查网关是否可达（1.2.3.4）—— 有助于判断网络物理层是否正常
    if not is_gateway_reachable():
        print("❌ 网关 1.2.3.4 不可达，网络异常。")
        return EXIT_NETWORK_ERROR

    print("✅ 网关可达，开始认证流程...")

    # 3. 构造完整用户名（账号 + 后缀）
    full_username = f"{USERNAME}{ACCOUNT_SUFFIX}"
    if not full_username or not PASSWORD:
        print("❌ 请在 .env 文件中配置 USERNAME 和 PASSWORD。")
        return EXIT_AUTH_ERROR

    # 4. 执行登录
    success, response = perform_login(full_username, PASSWORD)

    if not success:
        print(f"❌ 登录请求失败: {response}")
        return EXIT_LOGIN_FAILED

    print("📄 登录响应内容：")
    print(response)

    # 5. 解析响应（JSONP 格式，如 dr1004({...})）
    try:
        # 提取 JSON 部分
        match = re.search(r'dr1004\((.*)\)', response)
        if match:
            json_str = match.group(1)
            data = json.loads(json_str)
            result = data.get('result', -1)
            msga = data.get('msga', '')
            if result == 1:
                print("✅ 认证响应成功，等待网络生效...")
            else:
                print(f"❌ 认证失败: {msga}")
                return EXIT_AUTH_ERROR
        else:
            # 若不是 JSONP，尝试通过关键字判断
            if "authentication succeeded" in response.lower() or "success" in response.lower():
                print("✅ 认证响应成功，等待网络生效...")
            else:
                print("⚠️ 未知响应，继续等待...")
    except Exception as e:
        log_debug(f"解析响应异常: {e}")
        print("⚠️ 无法解析响应，继续等待...")

    # 6. 等待网络生效
    print("⏳ 等待 3 秒后检测外网...")
    time.sleep(3)

    # 7. 最终检测外网
    if is_internet_connected():
        print("🎉 登录成功！外网已连通。")
        return EXIT_SUCCESS
    else:
        print("⚠️ 登录请求已发送，但外网仍未连通，请检查。")
        return EXIT_UNKNOWN

if __name__ == "__main__":
    sys.exit(main())