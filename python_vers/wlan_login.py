#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import random
import socket
import base64
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, parse_qs, quote, urlencode

import requests
from dotenv import load_dotenv

# ---------- 加载环境变量 ----------
load_dotenv()

USERNAME = os.getenv("USERNAME", "")
PASSWORD = os.getenv("PASSWORD", "")
ACCOUNT_SUFFIX = os.getenv("ACCOUNT_SUFFIX", "@cmcc")
DEBUG = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
IPV6_ADDRESS = os.getenv("IPV6_ADDRESS", "")  # 留空则动态获取

# ---------- 返回码定义 ----------
EXIT_SUCCESS = 0          # 成功（已在线或登录成功）
EXIT_NETWORK_ERROR = 1    # 外网不可达且网关不可达（网络异常）
EXIT_PARSE_ERROR = 2      # 获取网关参数失败（解析错误）
EXIT_LOGIN_FAILED = 3     # 登录请求失败（网络错误或服务器无响应）
EXIT_AUTH_ERROR = 4       # 认证失败（账号密码错误或参数不匹配）
EXIT_UNKNOWN = 5          # 登录后外网仍未连通（可能未生效，需人工检查）

# ---------- 辅助函数 ----------
def log_debug(msg):
    if DEBUG:
        print(f"[DEBUG] {msg}")

def http_get_verbose(url, timeout=3, allow_redirects=False):
    try:
        resp = requests.get(url, timeout=timeout, allow_redirects=allow_redirects)
        return resp.status_code, resp.text, None
    except requests.RequestException as e:
        return None, None, e

def get_ipv6_dynamic():
    try:
        sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        sock.connect(("2001:4860:4860::8888", 80))
        ipv6 = sock.getsockname()[0]
        sock.close()
        if ipv6.startswith("fe80:") or ipv6 == "::1" or ipv6.startswith("::"):
            return ""
        return ipv6
    except Exception:
        return ""

# ---------- 功能函数 ----------
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
        if DEBUG and text:
            log_debug(f"响应片段: {text[:200].replace(chr(10), ' ')} ...")
        if ("百度" in text or "baidu" in text.lower()) and "WISPAccessGateway" not in text:
            return True
        else:
            log_debug("响应内容不含百度标志或仍为网关页面")
            return False
    except requests.RequestException as e:
        log_debug(f"请求异常: {e}")
        return False

def is_gateway_reachable():
    """检测网关 1.2.3.4 是否在线"""
    url = "http://1.2.3.4"
    log_debug(f"检测网关: GET {url}")
    status, content, err = http_get_verbose(url, timeout=3, allow_redirects=False)
    if err:
        log_debug(f"请求失败: {err}")
        return False
    log_debug(f"状态码: {status}")
    if status in (200, 301, 302, 303, 307):
        return True
    return False

def get_gateway_params():
    """
    访问网关获取认证参数。
    返回 (host, wlan_user_ip, wlan_ac_name, wlan_ac_ip, wlan_user_mac)
    若失败则返回 (None,)*5
    """
    try:
        resp = requests.get("http://1.2.3.4", timeout=5, allow_redirects=False)
        resp.raise_for_status()
    except Exception as e:
        log_debug(f"获取网关页面失败: {e}")
        return (None,) * 5

    if resp.status_code in (301, 302, 303, 307):
        location = resp.headers.get("Location")
        if not location:
            log_debug("重定向但无 Location 头")
            return (None,) * 5
        log_debug(f"重定向 Location: {location}")
        parsed = urlparse(location)
        params = parse_qs(parsed.query)
        wlan_user_ip = params.get("wlanuserip", [None])[0]
        wlan_ac_name = params.get("wlanacname", [None])[0]
        wlan_ac_ip = params.get("wlanacip", [None])[0]
        wlan_user_mac_raw = params.get("wlanusermac", [None])[0]
        host = parsed.hostname
    else:
        content = resp.text
        log_debug(f"响应状态码: {resp.status_code}")
        log_debug(f"响应内容片段: {content[:300]}")
        match = re.search(r"<!--\s*(.*?)\s*-->", content, re.DOTALL)
        if not match:
            log_debug("未找到 XML 注释内容")
            return (None,) * 5
        xml_str = match.group(1)
        try:
            root = ET.fromstring(xml_str)
        except ET.ParseError as e:
            log_debug(f"XML 解析失败: {e}")
            return (None,) * 5
        proxy = root.find("Proxy")
        if proxy is None:
            log_debug("未找到 Proxy 节点")
            return (None,) * 5
        next_url_elem = proxy.find("NextURL")
        if next_url_elem is None:
            log_debug("未找到 NextURL 节点")
            return (None,) * 5
        next_url = next_url_elem.text
        log_debug(f"获取 NextURL: {next_url}")
        parsed = urlparse(next_url)
        params = parse_qs(parsed.query)
        wlan_user_ip = params.get("wlanuserip", [None])[0]
        wlan_ac_name = params.get("wlanacname", [None])[0]
        wlan_ac_ip = params.get("wlanacip", [None])[0]
        wlan_user_mac_raw = params.get("wlanusermac", [None])[0]
        host = parsed.hostname

    if not all([wlan_user_ip, wlan_ac_name, wlan_ac_ip, wlan_user_mac_raw]):
        log_debug("缺少必要参数")
        return (None,) * 5

    wlan_user_mac = wlan_user_mac_raw.replace("-", "").replace(":", "").lower()
    if not host:
        host = "10.0.1.5"
    return host, wlan_user_ip, wlan_ac_name, wlan_ac_ip, wlan_user_mac

def perform_login(host, wlan_user_ip, wlan_ac_name, wlan_ac_ip, wlan_user_mac):
    """执行登录请求，返回 (success, response_text)"""
    login_url = f"http://{host}:801/eportal/portal/login"
    user_account_raw = f",0,{USERNAME}{ACCOUNT_SUFFIX}"
    user_password_raw = base64.b64encode(PASSWORD.encode()).decode()
    v = str(random.randint(1000, 9999))

    if IPV6_ADDRESS:
        ipv6 = IPV6_ADDRESS
    else:
        ipv6 = get_ipv6_dynamic()
        if not ipv6:
            ipv6 = ""
    print(f"📡 使用 IPv6: {ipv6 if ipv6 else '（无）'}")

    params_dict = {
        "callback": "dr1004",
        "login_method": "1",
        "user_account": user_account_raw,
        "user_password": user_password_raw,
        "wlan_user_ip": wlan_user_ip,
        "wlan_user_ipv6": ipv6,
        "wlan_user_mac": wlan_user_mac,
        "wlan_ac_ip": wlan_ac_ip,
        "wlan_ac_name": wlan_ac_name,
        "jsVersion": "4.2",
        "terminal_type": "3",
        "lang": "en",
        "v": v,
    }

    query_string = urlencode(params_dict, quote_via=quote)
    full_login_url = f"{login_url}?{query_string}"

    if DEBUG:
        log_debug(f"原始 user_account: {user_account_raw}")
        log_debug(f"编码后 user_account: {quote(user_account_raw)}")
        log_debug(f"完整请求 URL: {full_login_url}")

    try:
        resp = requests.get(full_login_url, timeout=5)
        resp.raise_for_status()
        return True, resp.text
    except requests.RequestException as e:
        log_debug(f"登录请求异常: {e}")
        return False, str(e)

# ---------- 主函数 ----------
def main():
    log_debug("===== 脚本启动 =====")
    print("🔍 正在检测网络连接状态...")

    # 1. 检查外网
    if is_internet_connected():
        print("✅ 外网已连通，无需认证。")
        return EXIT_SUCCESS

    print("❌ 外网不可达，可能未登录。")
    # 2. 检查网关
    if not is_gateway_reachable():
        print("❌ 网关 1.2.3.4 不可达，网络异常。")
        return EXIT_NETWORK_ERROR

    print("✅ 网关 1.2.3.4 可达，开始认证流程...")
    # 3. 获取认证参数
    params = get_gateway_params()
    if None in params:
        print("❌ 获取网关参数失败。")
        return EXIT_PARSE_ERROR
    host, wlan_user_ip, wlan_ac_name, wlan_ac_ip, wlan_user_mac = params
    print("✅ 成功获取认证参数。")

    # 4. 执行登录
    success, response = perform_login(host, wlan_user_ip, wlan_ac_name, wlan_ac_ip, wlan_user_mac)
    if not success:
        print(f"❌ 登录请求失败: {response}")
        return EXIT_LOGIN_FAILED

    print("📄 登录响应内容：")
    print(response)

    # 判断登录是否成功（根据响应内容）
    if "authentication succeeded" in response.lower() or "result\":1" in response:
        print("✅ 认证响应成功，等待网络生效...")
    elif "result\":0" in response or "fail" in response.lower():
        print("❌ 认证失败，请检查账号密码或后缀。")
        return EXIT_AUTH_ERROR
    else:
        print("⚠️ 未知响应，继续等待...")

    # 等待3秒，让网络生效
    print("⏳ 等待 3 秒后检测外网...")
    time.sleep(3)

    # 5. 最终检测外网
    if is_internet_connected():
        print("🎉 登录成功！外网已连通。")
        return EXIT_SUCCESS
    else:
        print("⚠️ 登录请求已发送，但外网仍未连通，请检查。")
        return EXIT_UNKNOWN

if __name__ == "__main__":
    sys.exit(main())