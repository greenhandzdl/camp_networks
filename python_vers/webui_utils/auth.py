# -*- coding: utf-8 -*-
"""WebUI 认证执行：任务启动/终止、自动认证后台循环"""

import os
import subprocess
import sys
import threading
import time

from .constants import (
    SCRIPT_PATH, CONFIG_DIR, SCRIPT_TIMEOUT,
    AUTO_CHECK_INTERVAL, DEFAULT_AUTO_DELAY, DEFAULT_AUTO_INTERVAL,
)
from .config import read_env
from .network import get_wifi_info

# ===================== 全局状态 =====================
_run_lock = threading.Lock()
_current_proc = None          # 当前运行中的认证子进程（Popen）
_proc_lock = threading.Lock()
_auto_state = {
    "connected": False,         # 是否连上目标 WiFi
    "connect_time": 0.0,        # 接入目标 WiFi 的时刻
    "next_run": 0.0,            # 下次计划执行的 unix 时间戳（0 表示无计划）
    "running_by_auto": False,   # 当前运行的任务是否由自动认证触发
}


def exec_login():
    """运行认证脚本，返回 (ok, output)；任务并发时返回 None，可被 stop_login() 终止"""
    if not _run_lock.acquire(blocking=False):
        return None
    global _current_proc
    try:
        proc = subprocess.Popen(
            [sys.executable, SCRIPT_PATH],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env={**os.environ, "DRCOM_CONFIG_DIR": CONFIG_DIR},
        )
        with _proc_lock:
            _current_proc = proc
        try:
            stdout, stderr = proc.communicate(timeout=SCRIPT_TIMEOUT)
            returncode = proc.returncode
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except OSError:
                pass
            stdout, stderr = proc.communicate()
            return False, f"认证脚本执行超时（{SCRIPT_TIMEOUT}s）"
        parts = [stdout.decode(errors="replace")] if stdout else []
        if stderr:
            parts.append(f"\n[STDERR]\n{stderr.decode(errors='replace')}")
        return returncode == 0, "".join(parts).strip()
    except Exception as e:
        return False, f"执行失败: {e}"
    finally:
        with _proc_lock:
            _current_proc = None
        _run_lock.release()


def stop_login():
    """终止当前运行中的认证任务（手动或自动均生效）"""
    with _proc_lock:
        p = _current_proc
    if p is None:
        return False
    try:
        p.kill()
        return True
    except OSError:
        return False


def get_run_status():
    """返回当前认证任务状态与自动认证调度状态（供 API 使用）"""
    with _proc_lock:
        running = _current_proc is not None
    now = time.time()
    next_run = _auto_state.get("next_run", 0.0)
    next_in = max(0, int(next_run - now)) if next_run > now else 0
    if running:
        source = "auto" if _auto_state.get("running_by_auto") else "manual"
    else:
        source = None
    return {
        "running": running,
        "source": source,
        "auto_connected": _auto_state.get("connected", False),
        "next_run_in": next_in,
        "has_schedule": next_run > now,
    }


def auto_loop():
    """后台循环：接入目标 ESSID 的 WiFi 延迟 auto_delay 秒后触发首次认证，
    之后按 auto_interval 间隔重跑，断开 WiFi 自动停止"""
    while True:
        time.sleep(AUTO_CHECK_INTERVAL)
        try:
            cfg = read_env()
            target = cfg.get("target_essid", "").strip()
            enabled = (cfg.get("auto_run") == "true" and target
                       and cfg.get("username") and cfg.get("password"))
            ssid = get_wifi_info().get("ssid", "")
            connected = bool(enabled) and ssid == target

            if not connected:
                # 未连接目标 WiFi：重置调度
                _auto_state["connected"] = False
                _auto_state["next_run"] = 0.0
                continue

            now = time.time()
            try:
                delay = max(0, int(cfg.get("auto_delay", DEFAULT_AUTO_DELAY)))
            except (ValueError, TypeError):
                delay = DEFAULT_AUTO_DELAY
            try:
                interval = max(1, int(cfg.get("auto_interval", DEFAULT_AUTO_INTERVAL))) * 60
            except (ValueError, TypeError):
                interval = DEFAULT_AUTO_INTERVAL * 60

            if not _auto_state["connected"]:
                # 刚接入目标 WiFi：记录接入时间，安排延迟后第一次执行
                _auto_state["connected"] = True
                _auto_state["connect_time"] = now
                _auto_state["next_run"] = now + delay
                print(f"[自动] 已接入 {target}，将在 {delay}s 后触发首次认证")
                continue

            # 已接入目标 WiFi：检查是否到达执行时间
            if _auto_state["next_run"] <= now:
                _auto_state["running_by_auto"] = True
                r = exec_login()
                _auto_state["running_by_auto"] = False
                if r is None:
                    print("[自动] 已有认证任务在运行，跳过本轮")
                else:
                    print(f"[自动] 认证{'成功' if r[0] else '失败'}\n{r[1]}")
                _auto_state["next_run"] = time.time() + interval
        except Exception as e:
            print(f"[自动] 检查异常: {e}")
