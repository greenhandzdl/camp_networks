#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dr.COM 校园网认证核心库（平台无关）

设计原则：
- 不 import subprocess、不执行任何 shell 命令
- 不依赖 dotenv（配置由调用方解析后传入）
- 只依赖 requests 和 Python 标准库

本模块提供认证全流程：网关参数获取、登录、登出、状态持久化，
被 wlan_login.py / wlan_logout.py（CLI 薄封装）和 Kivy APK 共用。
"""

from __future__ import annotations

import base64
import json
import os
import random
import re
import socket
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from typing import Optional
from urllib.parse import parse_qs, quote, urlencode, urlparse

import requests

# ---------- 返回码（与 CLI 脚本兼容）----------
EXIT_SUCCESS = 0
EXIT_NETWORK_ERROR = 1
EXIT_PARSE_ERROR = 2
EXIT_LOGIN_FAILED = 3
EXIT_AUTH_ERROR = 4
EXIT_UNKNOWN = 5


@dataclass
class DrComConfig:
    """认证配置。默认值与 config.env 一致。"""
    username: str = ""
    password: str = ""
    suffix: str = "@cmcc"
    auth_server: str = "10.0.1.5"
    redirect_server: str = "1.2.3.4"
    ipv6: str = ""
    timeout: int = 5
    debug: bool = False


@dataclass
class LoginState:
    """登录状态（认证参数 + 用户名），供登出/重认证复用。"""
    host: str = ""
    username: str = ""
    mac: str = ""
    ip: str = ""

    def save(self, path: str) -> bool:
        """保存状态到 JSON 文件。"""
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, ensure_ascii=False, indent=2)
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
            return True
        except (OSError, TypeError) as e:
            return False

    @classmethod
    def load(cls, path: str) -> Optional["LoginState"]:
        """从 JSON 文件加载状态，失败返回 None。"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(
                host=data.get("host", ""),
                username=data.get("username", ""),
                mac=data.get("mac", ""),
                ip=data.get("ip", ""),
            )
        except (OSError, json.JSONDecodeError, TypeError):
            return None


# ---------- 网络检测（纯 HTTP）----------

def check_internet(config: DrComConfig) -> bool:
    """检测外网是否已连通（通过百度）。"""
    try:
        resp = requests.get("http://baidu.com", timeout=config.timeout,
                            allow_redirects=True)
        if resp.status_code != 200:
            return False
        text = resp.text
        return ("百度" in text or "baidu" in text.lower()) \
               and "WISPAccessGateway" not in text
    except Exception:
        return False


def check_gateway(config: DrComConfig) -> bool:
    """检测校园网网关是否可达。"""
    try:
        resp = requests.get(f"http://{config.redirect_server}",
                            timeout=config.timeout, allow_redirects=False)
        return resp.status_code in (200, 301, 302, 303, 307)
    except Exception:
        return False


def probe_ipv6() -> str:
    """通过 UDP socket 探测本机全局 IPv6 地址。"""
    try:
        sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        sock.connect(("2001:4860:4860::8888", 80))
        addr = sock.getsockname()[0]
        sock.close()
        if addr.startswith("fe80") or addr == "::1" or addr.startswith("::"):
            return ""
        return addr
    except Exception:
        return ""


# ---------- 网关参数解析 ----------

def _parse_302(location: str):
    """解析 302 重定向 Location URL，返回 (host, ip, ac_name, ac_ip, mac)。"""
    parsed = urlparse(location)
    params = parse_qs(parsed.query)
    ip = params.get("wlanuserip", [None])[0]
    ac_name = params.get("wlanacname", [None])[0]
    ac_ip = params.get("wlanacip", [None])[0]
    mac_raw = params.get("wlanusermac", [None])[0]
    host = parsed.hostname
    if not all([ip, ac_name, ac_ip, mac_raw]):
        return (None,) * 5
    mac = mac_raw.replace("-", "").replace(":", "").lower()
    return host, ip, ac_name, ac_ip, mac


def _parse_xml_comment(content: str):
    """解析 XML 注释形式的网关响应，提取登录跳转参数。"""
    match = re.search(r"<!--\s*(.*?)\s*-->", content, re.DOTALL)
    if not match:
        return (None,) * 5
    try:
        root = ET.fromstring(match.group(1))
    except ET.ParseError:
        return (None,) * 5
    proxy = root.find("Proxy")
    if proxy is None:
        return (None,) * 5
    next_url_elem = proxy.find("NextURL")
    if next_url_elem is None or not next_url_elem.text:
        return (None,) * 5
    parsed = urlparse(next_url_elem.text)
    params = parse_qs(parsed.query)
    ip = params.get("wlanuserip", [None])[0]
    ac_name = params.get("wlanacname", [None])[0]
    ac_ip = params.get("wlanacip", [None])[0]
    mac_raw = params.get("wlanusermac", [None])[0]
    host = parsed.hostname
    if not all([ip, ac_name, ac_ip, mac_raw]):
        return (None,) * 5
    mac = mac_raw.replace("-", "").replace(":", "").lower()
    return host, ip, ac_name, ac_ip, mac


def fetch_gateway_params(config: DrComConfig):
    """
    请求网关，返回 (host, wlan_user_ip, wlan_ac_name, wlan_ac_ip, wlan_user_mac)。
    任一字段失败时返回 (None, None, None, None, None)。
    """
    try:
        resp = requests.get(f"http://{config.redirect_server}",
                            timeout=config.timeout, allow_redirects=False)
    except Exception:
        return (None,) * 5

    if resp.status_code in (301, 302, 303, 307):
        location = resp.headers.get("Location")
        if not location:
            return (None,) * 5
        host, ip, ac_name, ac_ip, mac = _parse_302(location)
    else:
        host, ip, ac_name, ac_ip, mac = _parse_xml_comment(resp.text)

    if not host:
        host = config.auth_server
    return host, ip, ac_name, ac_ip, mac


# ---------- 登录 ----------

def build_login_url(config: DrComConfig, host: str,
                    wlan_user_ip: str, wlan_ac_name: str,
                    wlan_ac_ip: str, wlan_user_mac: str) -> str:
    """构造登录 URL。"""
    user_account = f",0,{config.username}{config.suffix}"
    user_password = base64.b64encode(config.password.encode("utf-8")).decode("ascii")
    ipv6 = config.ipv6 or probe_ipv6() or ""
    params = {
        "callback": "dr1004",
        "login_method": "1",
        "user_account": user_account,
        "user_password": user_password,
        "wlan_user_ip": wlan_user_ip,
        "wlan_user_ipv6": ipv6,
        "wlan_user_mac": wlan_user_mac,
        "wlan_ac_ip": wlan_ac_ip,
        "wlan_ac_name": wlan_ac_name,
        "jsVersion": "4.2",
        "terminal_type": "3",
        "lang": "en",
        "v": str(random.randint(1000, 9999)),
    }
    return f"http://{host}:801/eportal/portal/login?{urlencode(params, quote_via=quote)}"


def perform_login(config: DrComConfig, host: str,
                  wlan_user_ip: str, wlan_ac_name: str,
                  wlan_ac_ip: str, wlan_user_mac: str) -> tuple[bool, str]:
    """执行登录 HTTP 请求，返回 (success, response_text_or_error)。"""
    url = build_login_url(config, host, wlan_user_ip, wlan_ac_name,
                          wlan_ac_ip, wlan_user_mac)
    try:
        resp = requests.get(url, timeout=config.timeout)
        resp.raise_for_status()
        return True, resp.text
    except requests.RequestException as e:
        return False, str(e)


def parse_login_response(text: str) -> tuple[bool, str]:
    """
    解析登录响应，返回 (success, message)。
    判定规则：包含 "authentication succeeded" 或 "result\":1" 视为成功。
    """
    if not text:
        return False, "响应为空"
    low = text.lower()
    if "authentication succeeded" in low or '"result":1' in low.replace(" ", ""):
        return True, "认证成功"
    if '"result":0' in low.replace(" ", ""):
        msg = ""
        m = re.search(r'"msg"\s*:\s*"([^"]*)"', text)
        if m:
            msg = m.group(1)
        return False, f"认证失败: {msg}" if msg else "认证失败"
    return False, f"未知响应: {text[:200]}"


# ---------- 登出 ----------

def build_logout_url(host: str, username: str, mac: str, ip: str) -> str:
    """构造登出 URL。注意 user_account 使用纯用户名（无 ,0, 前缀和 @suffix）。"""
    params = {
        "callback": "dr1002",
        "user_account": username,
        "wlan_user_mac": mac,
        "wlan_user_ip": ip,
        "jsVersion": "4.2",
        "v": str(random.randint(1000, 9999)),
        "lang": "en",
    }
    return f"http://{host}:801/eportal/portal/mac/unbind?{urlencode(params, quote_via=quote)}"


def perform_logout(host: str, username: str, mac: str, ip: str,
                   timeout: int = 5) -> tuple[bool, str]:
    """执行登出 HTTP 请求，返回 (success, response_text_or_error)。"""
    url = build_logout_url(host, username, mac, ip)
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        return True, resp.text
    except requests.RequestException as e:
        return False, str(e)


# ---------- 高级封装：一键登录/登出流程 ----------

def login_flow(config: DrComConfig, state_path: str) -> int:
    """
    一键登录：外网检测 → 网关探测 → 登录 → 验证 → 保存状态。
    返回 EXIT_* 码。进度信息通过回调传出（调用方可注入）。
    """
    if check_internet(config):
        return EXIT_SUCCESS  # 已通

    if not check_gateway(config):
        return EXIT_NETWORK_ERROR

    params = fetch_gateway_params(config)
    if any(p is None for p in params):
        return EXIT_PARSE_ERROR

    host, ip, ac_name, ac_ip, mac = params
    ok, resp = perform_login(config, host, ip, ac_name, ac_ip, mac)
    if not ok:
        return EXIT_LOGIN_FAILED

    ok_parse, msg = parse_login_response(resp)
    if not ok_parse:
        return EXIT_AUTH_ERROR

    time.sleep(1)
    state = LoginState(host=host, username=config.username, mac=mac, ip=ip)
    state.save(state_path)

    # 二次外网验证（可选）
    if check_internet(config):
        return EXIT_SUCCESS
    return EXIT_UNKNOWN


def logout_flow(state_path: str, timeout: int = 5) -> int:
    """
    一键登出：读取状态 → 发登出请求。
    返回 EXIT_SUCCESS / EXIT_NO_STATE(1) / EXIT_LOGOUT_FAILED(3)。
    """
    state = LoginState.load(state_path)
    if not state or not all([state.host, state.username, state.mac, state.ip]):
        return EXIT_NETWORK_ERROR  # 复用：参数不完整

    ok, _ = perform_logout(state.host, state.username, state.mac, state.ip,
                           timeout=timeout)
    return EXIT_SUCCESS if ok else EXIT_LOGIN_FAILED
