# -*- coding: utf-8 -*-
"""
Android 原生网络信息获取（通过 pyjnius 调 WifiManager）

仅在 Android 平台可用（Kivy APK 内）。
桌面/无 root 环境返回空值，UI 会降级显示。
"""

from __future__ import annotations
from typing import Dict


def _try_import_android():
    """尝试导入 pyjnius，非 Android 环境返回 None。"""
    try:
        from jnius import autoclass
        return autoclass
    except ImportError:
        return None


def get_wifi_info() -> Dict:
    """
    获取当前 Wi-Fi 信息：{ssid, ip, mac, ipv6}
    注意：Android 10+ MAC 地址 API 返回 02:00:00:00:00:00，
    认证主流程 MAC 来自网关重定向参数，此处仅用于展示。
    """
    autoclass = _try_import_android()
    if autoclass is None:
        return {"ssid": "", "ip": "", "mac": "", "ipv6": ""}

    result = {"ssid": "", "ip": "", "mac": "", "ipv6": ""}
    try:
        Context = autoclass("android.content.Context")
        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        wifi_manager = activity.getSystemService(Context.WIFI_SERVICE)
        info = wifi_manager.getConnectionInfo()
        if info is None:
            return result

        # SSID
        ssid = info.getSSID()
        if ssid and ssid not in ("<unknown ssid>", "0x", "<NULL>"):
            result["ssid"] = ssid.strip('"')

        # IP（int → dotted）
        ip_int = info.getIpAddress()
        if ip_int != 0:
            ip_bytes = [
                (ip_int >> (i * 8)) & 0xFF for i in range(4)
            ]
            result["ip"] = ".".join(str(b) for b in ip_bytes)

        # MAC（Android 10+ 通常返回 02:00:00:00:00:00）
        mac = info.getMacAddress()
        if mac and mac != "02:00:00:00:00:00":
            result["mac"] = mac.upper().replace(":", "")

    except Exception:
        pass

    # IPv6（通过 socket 探测，复用 drcom_core 逻辑）
    try:
        import drcom_core
        result["ipv6"] = drcom_core.probe_ipv6()
    except Exception:
        pass

    return result
