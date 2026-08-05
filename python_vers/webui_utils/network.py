# -*- coding: utf-8 -*-
"""WebUI 网络信息：WiFi SSID/BSSID 获取、IP 地址枚举"""

import re
import socket
import subprocess

from .constants import API_TIMEOUT, WLAN_IFACE


def get_wifi_info():
    """通过 dumpsys 获取当前 WiFi 的 SSID/BSSID"""
    try:
        out = subprocess.run(["dumpsys", "wifi"], capture_output=True, text=True,
                             timeout=API_TIMEOUT).stdout
        m = re.search(r"BSSID:\s*([0-9a-fA-F:]{17})", out)
        bssid = m.group(1) if m else ""
        if bssid.lower() == "02:00:00:00:00:00":  # Android 无权限/未连接时的占位值
            bssid = ""
        m = re.search(r"SSID:\s*(\S+)", out)
        ssid = m.group(1).strip('",') if m else ""
        if ssid.lower() in ("0x", "<unknown", "null") or "unknown" in ssid.lower():
            ssid = ""
        return {"ssid": ssid, "bssid": bssid}
    except Exception:
        return {"ssid": "", "bssid": ""}


def _get_ipv6_via_socket():
    """通过 UDP socket 探测本机 IPv6 出口地址"""
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


def _scan_all_interfaces_ipv6():
    """扫描所有网络接口，收集全局 IPv6 地址作为兜底"""
    addrs = []
    try:
        out = subprocess.run(["ip", "addr", "show"], capture_output=True,
                             text=True, timeout=API_TIMEOUT).stdout
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("inet6 "):
                addr = line.split()[1].split("/")[0]
                if not addr.startswith("fe80") and addr != "::1":
                    addrs.append(addr)
    except Exception:
        pass
    return addrs


def get_ip_addresses():
    """获取 wlan 接口的 IPv4 地址和系统 IPv6 出口地址"""
    ipv4, ipv6 = [], []
    # 从 wlan 接口获取 IPv4
    try:
        out = subprocess.run(["ip", "addr", "show", WLAN_IFACE], capture_output=True,
                             text=True, timeout=API_TIMEOUT).stdout
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("inet "):
                ipv4.append(line.split()[1].split("/")[0])
            elif line.startswith("inet6 "):
                addr = line.split()[1].split("/")[0]
                if not addr.startswith("fe80"):
                    ipv6.append(addr)
    except Exception:
        pass
    # IPv6: 优先 socket 探测出口地址（WiFi 可能无全局 IPv6，移动数据有）
    if not ipv6:
        sock_addr = _get_ipv6_via_socket()
        if sock_addr:
            ipv6.append(sock_addr)
    # 兜底: 扫描所有接口
    if not ipv6:
        ipv6 = _scan_all_interfaces_ipv6()
    return {"ipv4": ipv4, "ipv6": ipv6}
