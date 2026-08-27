# -*- coding: utf-8 -*-
"""
Android 原生网络信息获取（通过 pyjnius 调 WifiManager）

仅在 Android 平台可用（Kivy APK 内）。
桌面/无 root 环境返回空值，UI 会降级显示。
"""

from __future__ import annotations
import re
import socket
import subprocess
from typing import Dict


def _try_import_android():
    """尝试导入 pyjnius，非 Android 环境返回 None。"""
    try:
        from jnius import autoclass
        return autoclass
    except ImportError:
        return None


def _invalid_ssid(ssid: str) -> bool:
    """判断 SSID 是否为无效值（Android 权限不足/未连接时的占位值）。"""
    if not ssid:
        return True
    s = ssid.strip().strip('"').lower()
    if s in ("", "0x", "<null>", "<unknown ssid>"):
        return True
    if "unknown" in s:
        return True
    return False


def _get_ssid_from_dumpsys() -> str:
    """通过 dumpsys wifi 获取 SSID（Android 10+ 的权限友好方式）。"""
    try:
        out = subprocess.run(
            ["dumpsys", "wifi"], capture_output=True, text=True, timeout=3
        ).stdout
        m = re.search(r"mWifiInfo\s+SSID:\s*(\S+)", out)
        if not m:
            m = re.search(r"SSID:\s*(\S+)", out)
        ssid = m.group(1).strip('",') if m else ""
        return "" if _invalid_ssid(ssid) else ssid
    except Exception:
        return ""


def _get_ssid_via_connectivity(autoclass) -> str:
    """通过 ConnectivityManager + NetworkCapabilities 获取 SSID（Android 10+）。"""
    try:
        Context = autoclass("android.content.Context")
        NetworkCapabilities = autoclass("android.net.NetworkCapabilities")
        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        cm = activity.getSystemService(Context.CONNECTIVITY_SERVICE)
        network = cm.getActiveNetwork()
        if network is None:
            return ""
        caps = cm.getNetworkCapabilities(network)
        if caps is None:
            return ""
        transport_info = caps.getTransportInfo()
        if transport_info is None:
            return ""
        # WifiInfo class has getSSID()
        WifiInfo = autoclass("android.net.wifi.WifiInfo")
        ssid = transport_info.getSSID()
        return "" if _invalid_ssid(ssid) else ssid.strip('"')
    except Exception:
        return ""


def _probe_ipv6_socket() -> str:
    """通过 UDP socket 探测本机 IPv6 出口地址。"""
    try:
        sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        sock.connect(("2001:4860:4860::8888", 80))
        addr = sock.getsockname()[0]
        sock.close()
        if addr.startswith("fe80") or addr.startswith("::"):
            return ""
        return addr
    except Exception:
        return ""


def _probe_ipv6_interfaces() -> str:
    """扫描网络接口获取全局 IPv6 地址作为兜底。"""
    try:
        out = subprocess.run(
            ["ip", "addr", "show"], capture_output=True, text=True, timeout=3
        ).stdout
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("inet6 "):
                addr = line.split()[1].split("/")[0]
                if not addr.startswith("fe80") and addr != "::1":
                    return addr
    except Exception:
        pass
    return ""


def get_wifi_info() -> Dict:
    """
    获取当前 Wi-Fi 信息：{ssid, bssid, ip, mac, ipv6, ipv4, ipv6_list}
    注意：Android 10+MAC 地址 API 返回 02:00:00:00:00:00，
    认证主流程 MAC 来自网关重定向参数，此处仅用于展示。
    """
    autoclass = _try_import_android()
    if autoclass is None:
        return {"ssid": "", "bssid": "", "ip": "", "mac": "",
                "ipv6": "", "ipv4": [], "ipv6_list": []}

    result = {"ssid": "", "bssid": "", "ip": "", "mac": "",
              "ipv6": "", "ipv4": [], "ipv6_list": []}
    try:
        Context = autoclass("android.content.Context")
        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        wifi_manager = activity.getSystemService(Context.WIFI_SERVICE)
        info = wifi_manager.getConnectionInfo()
        if info is not None:
            # SSID（优先 getConnectionInfo，无效则走回退）
            ssid = info.getSSID()
            if not _invalid_ssid(ssid):
                result["ssid"] = ssid.strip('"')

            # BSSID
            bssid = info.getBSSID()
            if bssid and bssid != "02:00:00:00:00:00":
                result["bssid"] = bssid

            # IP（int → dotted）
            ip_int = info.getIpAddress()
            if ip_int != 0:
                ip_bytes = [
                    (ip_int >> (i * 8)) & 0xFF for i in range(4)
                ]
                result["ip"] = ".".join(str(b) for b in ip_bytes)
                result["ipv4"] = [result["ip"]]

            # MAC（Android 10+ 通常返回 02:00:00:00:00:00）
            mac = info.getMacAddress()
            if mac and mac != "02:00:00:00:00:00":
                result["mac"] = mac.upper().replace(":", "")
    except Exception:
        pass

    # SSID 回退链：getConnectionInfo → NetworkCapabilities → dumpsys
    if not result["ssid"]:
        ssid = _get_ssid_via_connectivity(autoclass)
        if ssid:
            result["ssid"] = ssid
    if not result["ssid"]:
        ssid = _get_ssid_from_dumpsys()
        if ssid:
            result["ssid"] = ssid

    # IPv6：优先 drcom_core.probe_ipv6()，回退 socket 探测，再回退接口扫描
    ipv6 = ""
    try:
        import drcom_core
        ipv6 = drcom_core.probe_ipv6() or ""
    except Exception:
        pass
    if not ipv6:
        ipv6 = _probe_ipv6_socket()
    if not ipv6:
        ipv6 = _probe_ipv6_interfaces()
    result["ipv6"] = ipv6
    result["ipv6_list"] = [ipv6] if ipv6 else []

    return result
