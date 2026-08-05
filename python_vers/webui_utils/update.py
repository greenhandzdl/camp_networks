# -*- coding: utf-8 -*-
"""WebUI 更新检测：按配置渠道查询、CDN/GitHub 下载"""

from .constants import GITHUB_REPO, CDN_BASE, API_TIMEOUT, UA, SCRIPT_TIMEOUT

try:
    import requests
except ImportError:
    requests = None

# 渠道定义：名称 → update.json URL
CHANNELS = {
    "GitHub": f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/update.json",
    "CDN":    f"{CDN_BASE}/{GITHUB_REPO}@main/update.json",
}


def check_update(channel="GitHub"):
    """查询指定渠道的更新，返回 (info_dict, error_string)"""
    if requests is None:
        return None, "requests 库未安装"
    url = CHANNELS.get(channel)
    if not url:
        return None, f"未知渠道: {channel}"
    try:
        resp = requests.get(url, timeout=API_TIMEOUT, headers={"User-Agent": UA})
        resp.raise_for_status()
        d = resp.json()
        tag = d.get("version", "")
        vc = int(d.get("versionCode", 0))
        return {
            "channel": channel,
            "tag": tag, "versionCode": vc,
            "html_url": d.get("changelog", ""),
            "zip_cdn": f"{CDN_BASE}/{GITHUB_REPO}@releases/{tag}.zip",
            "zip_direct": f"https://github.com/{GITHUB_REPO}/releases/download/{tag}/drcom-wlan-login.zip",
        }, None
    except Exception as e:
        return None, str(e)


def download_update(info, dl_dir):
    """下载更新包到指定目录，返回 (ok, message)"""
    if requests is None:
        return False, "requests 库未安装", ""
    import os
    os.makedirs(dl_dir, exist_ok=True)
    dl_path = os.path.join(dl_dir, "drcom_update.zip")

    last_err, dl_source = "", ""
    # 下载：CDN 优先，失败则 GitHub 直连兜底
    for dl_source, url in (("CDN", info["zip_cdn"]), ("GitHub", info["zip_direct"])):
        try:
            resp = requests.get(url, timeout=SCRIPT_TIMEOUT, stream=True,
                                headers={"User-Agent": UA})
            resp.raise_for_status()
            with open(dl_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            break
        except Exception as e:
            last_err = str(e)
    else:
        return False, f"下载失败（CDN/GitHub 均不可用）: {last_err}", ""

    size_kb = os.path.getsize(dl_path) / 1024
    out = f"已下载: {info['tag']} ({size_kb:.1f} KB)\n"
    out += f"渠道: {info['channel']} | 下载: {dl_source}\n"
    out += f"保存到: {dl_path}\n"
    out += "请在 Magisk Manager 中从本地安装此 zip 文件完成更新。"
    return True, out, ""
