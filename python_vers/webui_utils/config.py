# -*- coding: utf-8 -*-
"""WebUI 配置读写：config.env 解析/写入、module.prop 解析、账号/渠道管理"""

import json
import os

from .constants import (
    ENV_DEFAULTS, ENV_KEYS, ENV_PATH, CONFIG_DIR,
    DEFAULT_PORT, PROP_PATH,
    ACCOUNTS_PATH, CHANNELS_PATH,
    DEFAULT_CHANNELS, BUILTIN_CHANNEL_SUFFIXES,
)


def _parse_env(path):
    """通用 .env 文件解析"""
    cfg = dict(ENV_DEFAULTS)
    if os.path.exists(path):
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    cfg[k.lower()] = v
    return cfg


def read_env():
    return _parse_env(ENV_PATH)


def write_env(**kwargs):
    """合并写入 config.env（保留未传入的已有值）"""
    cfg = read_env()
    cfg.update(kwargs)
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(ENV_PATH, "w") as f:
        for key in ENV_KEYS:
            f.write(f"{key.upper()}={cfg.get(key, '')}\n")
    return cfg


def read_port():
    """从 config.env 读取端口，无效则返回默认值"""
    try:
        p = int(read_env().get("port", DEFAULT_PORT))
        return p if 1 <= p <= 65535 else DEFAULT_PORT
    except (ValueError, TypeError):
        return DEFAULT_PORT


def read_module_prop():
    prop = {}
    if os.path.exists(PROP_PATH):
        with open(PROP_PATH, "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    prop[k] = v
    return prop


# ===================== 账号记忆 =====================

def _read_json(path):
    """读取 JSON 文件，不存在则返回空列表/字典"""
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        return json.load(f)


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_accounts():
    data = _read_json(ACCOUNTS_PATH)
    return data if isinstance(data, list) else []


def write_accounts(accounts):
    _write_json(ACCOUNTS_PATH, accounts)


def add_account(username, password):
    if not username:
        return False, "用户名不能为空"
    accounts = read_accounts()
    for a in accounts:
        if a.get("username") == username:
            return False, "账号已存在"
    accounts.append({"username": username, "password": password})
    write_accounts(accounts)
    return True, "保存成功"


def delete_account(index):
    accounts = read_accounts()
    if not (0 <= index < len(accounts)):
        return False, "索引无效"
    accounts.pop(index)
    write_accounts(accounts)
    return True, "删除成功"


# ===================== 渠道映射 =====================

def read_channels():
    data = _read_json(CHANNELS_PATH)
    if not isinstance(data, dict) or not data:
        # 首次读取：写入并返回默认渠道
        write_channels(dict(DEFAULT_CHANNELS))
        return dict(DEFAULT_CHANNELS)
    # 确保内置渠道不丢失
    merged = dict(DEFAULT_CHANNELS)
    merged.update(data)
    if set(merged.items()) != set(data.items()):
        write_channels(merged)
    return merged


def write_channels(channels):
    _write_json(CHANNELS_PATH, channels)


def add_channel(suffix, label):
    if not suffix:
        return False, "后缀不能为空"
    if suffix in BUILTIN_CHANNEL_SUFFIXES:
        return False, "内置渠道不可新增"
    channels = read_channels()
    if suffix in channels:
        return False, "该后缀已存在"
    channels[suffix] = label
    write_channels(channels)
    return True, "添加成功"


def delete_channel(suffix):
    if suffix in BUILTIN_CHANNEL_SUFFIXES:
        return False, "内置渠道不可删除"
    channels = read_channels()
    if suffix not in channels:
        return False, "渠道不存在"
    del channels[suffix]
    write_channels(channels)
    return True, "删除成功"


def modify_channel(suffix, label):
    channels = read_channels()
    if suffix not in channels:
        return False, "渠道不存在"
    channels[suffix] = label
    write_channels(channels)
    return True, "修改成功"
