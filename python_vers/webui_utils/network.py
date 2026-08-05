# -*- coding: utf-8 -*-
"""WebUI 网络信息：WiFi SSID/BSSID 获取、IP 地址枚举"""

import re
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


def get_ip_addresses():
    """获取 wlan 接口的 IPv4/IPv6 地址"""
    ipv4, ipv6 = [], []
    try:
        out = subprocess.run(["ip", "addr", "show", WLAN_IFACE], capture_output=True,
                             text=True, timeout=API_TIMEOUT).stdout
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("inet "):
                ipv4.append(line.split()[1].split("/")[0])
            elif line.startswith("inet6 "):
                addr = line.split()[1].split("/")[0]
                if not addr.startswith("fe80"):  # 跳过链路本地地址
                    ipv6.append(addr)
    except Exception:
        pass
    return {"ipv4": ipv4, "ipv6": ipv6}
