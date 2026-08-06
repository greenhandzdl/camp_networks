# -*- coding: utf-8 -*-
"""WebUI 常量定义：路径、行为参数、配置默认值"""

import os

# ===================== 路径常量 =====================
# webui_utils/ 目录
_UTILS_DIR = os.path.dirname(os.path.abspath(__file__))
# python_vers/ 目录（webui.py 所在目录）
SCRIPT_DIR = os.path.dirname(_UTILS_DIR)
# 模块目录：优先从 start_webui.sh 导出的环境变量获取（修复 Magisk overlay 路径问题）
MOD_DIR = os.environ.get(
    "DRCOM_MOD_DIR",
    os.path.dirname(os.path.dirname(os.path.dirname(_UTILS_DIR))),
)
# 配置目录默认使用独立数据目录（刷入新版模块不会丢失）
CONFIG_DIR = os.environ.get("DRCOM_CONFIG_DIR", "/data/adb/drcom-wlan-login")
ENV_PATH = os.path.join(CONFIG_DIR, "config.env")
PROP_PATH = os.path.join(MOD_DIR, "module.prop")
SCRIPT_PATH = os.path.join(SCRIPT_DIR, "wlan_login.py")
LOGOUT_SCRIPT_PATH = os.path.join(SCRIPT_DIR, "wlan_logout.py")
ACCOUNTS_PATH = os.path.join(CONFIG_DIR, "accounts.json")
CHANNELS_PATH = os.path.join(CONFIG_DIR, "channels.json")

DEFAULT_CHANNELS = {
    "@cmcc": "中国移动",
    "@unicom": "中国联通",
    "@telecom": "中国电信",
    "@glgd": "中国广电",
    "": "校园网",
}
BUILTIN_CHANNEL_SUFFIXES = set(DEFAULT_CHANNELS.keys())

# ===================== 行为常量 =====================
DEFAULT_PORT = 38080
DEFAULT_SUFFIX = "@cmcc"
DEFAULT_LOG_FILE = "/data/local/tmp/drcom_webui.log"
DEFAULT_DOWNLOAD_DIR = "/sdcard/Download"   # 更新包下载目录（可在 WebUI 修改）
DEFAULT_AUTO_INTERVAL = 5     # 自动认证间隔（分钟）
DEFAULT_AUTO_DELAY = 5        # 接入目标 WiFi 后延迟秒数再触发第一次认证（等待 DHCP 等）
DEFAULT_AUTH_SERVER = "10.0.1.5"      # 认证服务器 IP
DEFAULT_REDIRECT_SERVER = "1.2.3.4"   # 网关重定向地址（用于检测网络状态和获取认证参数）
AUTO_CHECK_INTERVAL = 10      # 自动认证轮询 WiFi 状态周期（秒）
GITHUB_REPO = "greenhandzdl/camp_networks_magisk"
CDN_BASE = "https://cdn.jsdelivr.net/gh"   # jsDelivr CDN（国内访问 GitHub 不稳定，优先走 CDN）
WLAN_IFACE = "wlan0"
SCRIPT_TIMEOUT = 60       # 认证脚本超时（秒）
API_TIMEOUT = 10          # 系统命令/API 超时（秒）
SHUTDOWN_DELAY = 1.5      # 端口变更后关闭延迟（秒）
LOG_TAIL_LINES = 100      # WebUI 查看日志显示行数
UA = "DrCOM-Magisk"

# 所有可配置项统一定义在此（写入 config.env，_ENV_KEYS 定义写入顺序）
ENV_DEFAULTS = {
    "username": "", "password": "", "suffix": DEFAULT_SUFFIX,
    "debug": "false", "port": str(DEFAULT_PORT),
    "log_file": DEFAULT_LOG_FILE, "download_dir": DEFAULT_DOWNLOAD_DIR,
    "auto_run": "false", "target_essid": "", "auto_interval": str(DEFAULT_AUTO_INTERVAL),
    "auto_delay": str(DEFAULT_AUTO_DELAY),
    "update_channel": "GitHub",
    "auth_server": DEFAULT_AUTH_SERVER,
    "redirect_server": DEFAULT_REDIRECT_SERVER,
    "auto_open_webui": "false",
}
ENV_KEYS = list(ENV_DEFAULTS)
