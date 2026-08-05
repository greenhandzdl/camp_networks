# -*- coding: utf-8 -*-
"""WebUI 配置读写：config.env 解析/写入、module.prop 解析"""

import os

from .constants import (
    ENV_DEFAULTS, ENV_KEYS, ENV_PATH, CONFIG_DIR,
    DEFAULT_PORT, PROP_PATH,
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
