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

# ---------- 配置文件路径：从环境变量获取模块根目录 ----------
CONFIG_DIR = os.environ.get("DRCOM_CONFIG_DIR", "/data/adb/modules/drcom-wlan-login")
ENV_PATH = os.path.join(CONFIG_DIR, "config.env")

if not os.path.exists(ENV_PATH):
    print("❌ 配置文件 config.env 不存在，请先通过 WebUI 保存设置。")
    sys.exit(1)

load_dotenv(ENV_PATH)

USERNAME = os.getenv("USERNAME", "")
PASSWORD = os.getenv("PASSWORD", "")
ACCOUNT_SUFFIX = os.getenv("ACCOUNT_SUFFIX", "@cmcc")
DEBUG = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
IPV6_ADDRESS = os.getenv("IPV6_ADDRESS", "")
AUTH_SERVER = os.getenv("AUTH_SERVER", "10.0.1.5")
REDIRECT_SERVER = os.getenv("REDIRECT_SERVER", "1.2.3.4")

# ---------- 返回码 ----------
EXIT_SUCCESS = 0
EXIT_NETWORK_ERROR = 1
EXIT_PARSE_ERROR = 2
EXIT_LOGIN_FAILED = 3
EXIT_AUTH_ERROR = 4
EXIT_UNKNOWN = 5

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

# ---------- 网络检测 ----------
def is_internet_connected():
    url = "http://baidu.com"
    log_debug(f"检测外网: GET {url}")
    try:
        resp = requests.get(url, timeout=5, allow_redirects=True)
        if resp.status_code != 200:
            return False
        text = resp.text
        if ("百度" in text or "baidu" in text.lower()) and "WISPAccessGateway" not in text:
            return True
        return False
    except:
        return False

def is_gateway_reachable():
    url = f"http://{REDIRECT_SERVER}"
    log_debug(f"检测网关: GET {url}")
    status, content, err = http_get_verbose(url, timeout=3, allow_redirects=False)
    if err:
        return False
    return status in (200, 301, 302, 303, 307)

def get_gateway_params():
    try:
        resp = requests.get(f"http://{REDIRECT_SERVER}", timeout=5, allow_redirects=False)
        resp.raise_for_status()
    except Exception as e:
        log_debug(f"获取网关页面失败: {e}")
        return (None,) * 5

    if resp.status_code in (301, 302, 303, 307):
        location = resp.headers.get("Location")
        if not location:
            return (None,) * 5
        parsed = urlparse(location)
        params = parse_qs(parsed.query)
        wlan_user_ip = params.get("wlanuserip", [None])[0]
        wlan_ac_name = params.get("wlanacname", [None])[0]
        wlan_ac_ip = params.get("wlanacip", [None])[0]
        wlan_user_mac_raw = params.get("wlanusermac", [None])[0]
        host = parsed.hostname
    else:
        content = resp.text
        match = re.search(r"<!--\s*(.*?)\s*-->", content, re.DOTALL)
        if not match:
            return (None,) * 5
        xml_str = match.group(1)
        try:
            root = ET.fromstring(xml_str)
        except ET.ParseError:
            return (None,) * 5
        proxy = root.find("Proxy")
        if proxy is None:
            return (None,) * 5
        next_url_elem = proxy.find("NextURL")
        if next_url_elem is None:
            return (None,) * 5
        next_url = next_url_elem.text
        parsed = urlparse(next_url)
        params = parse_qs(parsed.query)
        wlan_user_ip = params.get("wlanuserip", [None])[0]
        wlan_ac_name = params.get("wlanacname", [None])[0]
        wlan_ac_ip = params.get("wlanacip", [None])[0]
        wlan_user_mac_raw = params.get("wlanusermac", [None])[0]
        host = parsed.hostname

    if not all([wlan_user_ip, wlan_ac_name, wlan_ac_ip, wlan_user_mac_raw]):
        return (None,) * 5
    wlan_user_mac = wlan_user_mac_raw.replace("-", "").replace(":", "").lower()
    if not host:
        host = AUTH_SERVER
    return host, wlan_user_ip, wlan_ac_name, wlan_ac_ip, wlan_user_mac

def perform_login(host, wlan_user_ip, wlan_ac_name, wlan_ac_ip, wlan_user_mac):
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
    log_debug(f"完整请求 URL: {full_login_url}")

    try:
        resp = requests.get(full_login_url, timeout=5)
        resp.raise_for_status()
        return True, resp.text
    except requests.RequestException as e:
        log_debug(f"登录请求异常: {e}")
        return False, str(e)

# ---------- 主流程 ----------
def main():
    print("🔍 正在检测网络状态...")
    if is_internet_connected():
        print("✅ 外网已连通，无需认证。")
        return EXIT_SUCCESS

    if not is_gateway_reachable():
        print(f"❌ 网关 {REDIRECT_SERVER} 不可达，网络异常。")
        return EXIT_NETWORK_ERROR

    print("✅ 网关可达，开始获取认证参数...")
    params = get_gateway_params()
    if None in params:
        print("❌ 获取网关参数失败。")
        return EXIT_PARSE_ERROR

    host, wlan_user_ip, wlan_ac_name, wlan_ac_ip, wlan_user_mac = params
    print("✅ 获取参数成功，执行登录...")

    success, response = perform_login(host, wlan_user_ip, wlan_ac_name, wlan_ac_ip, wlan_user_mac)
    if not success:
        print(f"❌ 登录请求失败: {response}")
        return EXIT_LOGIN_FAILED

    print("📄 登录响应：", response)
    if "authentication succeeded" in response.lower() or "result\":1" in response:
        print("✅ 认证成功，等待生效...")
    else:
        print("⚠️ 未知响应，可能失败。")
        return EXIT_AUTH_ERROR

    time.sleep(3)
    if is_internet_connected():
        print("🎉 登录成功！外网已连通。")
        return EXIT_SUCCESS
    else:
        print("⚠️ 外网仍未连通，请检查。")
        return EXIT_UNKNOWN

if __name__ == "__main__":
    sys.exit(main())