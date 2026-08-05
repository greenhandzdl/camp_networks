# -*- coding: utf-8 -*-
"""WebUI 认证执行：任务启动/终止、自动认证后台循环"""

import os
import subprocess
import sys
import threading
import time

from .constants import (
    AUTO_CHECK_INTERVAL, DEFAULT_AUTO_DELAY, DEFAULT_AUTO_INTERVAL,
)
from . import constants as _C
from .config import read_env
from .network import get_wifi_info

# ===================== 全局状态 =====================
_run_lock = threading.Lock()
_current_proc = None          # 当前运行中的认证子进程（Popen）
_proc_lock = threading.Lock()
_task_id = 0
_task_result = None           # {"ok": bool, "output": str} or None
_task_lock = threading.Lock()
_auto_state = {
    "connected": False,
    "connect_time": 0.0,
    "next_run": 0.0,
    "running_by_auto": False,
}


def _write_log(output):
    """将认证脚本输出追加写入日志文件"""
    log_path = ""
    try:
        log_path = read_env().get("log_file", "") or "/data/local/tmp/drcom_webui.log"
        log_dir = os.path.dirname(log_path)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        with open(log_path, "a", errors="replace") as f:
            f.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
            f.write(output + "\n")
    except Exception as e:
        print(f"[日志写入失败] path={log_path!r}, error={e}")


def _run_login_thread(is_auto=False):
    """后台线程：运行认证脚本，结果存入 _task_result"""
    global _current_proc
    output = ""
    ok = False
    try:
        proc = subprocess.Popen(
            [sys.executable, _C.SCRIPT_PATH],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env={**os.environ, "DRCOM_CONFIG_DIR": _C.CONFIG_DIR},
        )
        with _proc_lock:
            _current_proc = proc
        try:
            raw, _ = proc.communicate(timeout=_C.SCRIPT_TIMEOUT)
            returncode = proc.returncode
            output = raw.decode(errors="replace").strip() if raw else ""
            ok = returncode == 0
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except OSError:
                pass
            raw, _ = proc.communicate()
            captured = raw.decode(errors="replace").strip() if raw else ""
            output = f"认证脚本执行超时（{_C.SCRIPT_TIMEOUT}s）"
            if captured:
                output += f"\n--- 超时前输出 ---\n{captured}"
            ok = False
    except Exception as e:
        output = f"执行失败: {e}"
        ok = False
    finally:
        # 确保有输出内容（即使脚本无输出也记录状态）
        if not output:
            output = f"[脚本无输出] returncode={ok}, 请检查 wlan_login.py 是否正常"
        with _task_lock:
            global _task_result
            _task_result = {"ok": ok, "output": output}
        # 无论成功/失败/超时/异常，都写入日志
        _write_log(output)
        if is_auto:
            print(f"[自动] 认证{'成功' if ok else '失败'}\n{output}")
        with _proc_lock:
            _current_proc = None
        _run_lock.release()


def start_login():
    """启动认证任务（非阻塞），返回 task_id 或 None（已有任务运行）"""
    global _task_id
    if not _run_lock.acquire(blocking=False):
        return None
    with _task_lock:
        _task_id += 1
        _task_result = None
    tid = _task_id
    threading.Thread(target=_run_login_thread, daemon=True).start()
    return tid


def get_task_result(task_id):
    """获取任务结果，返回 {"ok", "output"} 或 None（未完成/任务不存在）"""
    if task_id != _task_id:
        return None
    with _task_lock:
        return _task_result


def stop_login():
    """终止当前运行中的认证任务"""
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

    # 实时检测自动认证配置与 WiFi 状态
    cfg = read_env()
    target = cfg.get("target_essid", "").strip()
    auto_enabled = (cfg.get("auto_run") == "true" and target
                    and cfg.get("username") and cfg.get("password"))
    if auto_enabled and not _auto_state.get("connected"):
        try:
            ssid = get_wifi_info().get("ssid", "")
            if ssid and ssid == target:
                return {
                    "running": running, "source": source,
                    "auto_enabled": True,
                    "auto_connected": False,
                    "waiting_first": True,
                    "next_run_in": 0, "has_schedule": False,
                }
        except Exception:
            pass

    return {
        "running": running,
        "source": source,
        "auto_enabled": auto_enabled,
        "auto_connected": _auto_state.get("connected", False),
        "waiting_first": False,
        "next_run_in": next_in,
        "has_schedule": next_run > now,
    }


def auto_loop():
    """后台循环：接入目标 ESSID 的 WiFi 延迟 auto_delay 秒后触发首次认证，
    之后按 auto_interval 间隔重跑，断开 WiFi 自动停止"""
    while True:
        try:
            cfg = read_env()
            target = cfg.get("target_essid", "").strip()
            enabled = (cfg.get("auto_run") == "true" and target
                       and cfg.get("username") and cfg.get("password"))
            ssid = get_wifi_info().get("ssid", "")
            connected = bool(enabled) and ssid == target

            if not connected:
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
                _auto_state["connected"] = True
                _auto_state["connect_time"] = now
                _auto_state["next_run"] = now + delay
                print(f"[自动] 已接入 {target}，将在 {delay}s 后触发首次认证")
                continue

            if _auto_state["next_run"] <= now:
                _auto_state["running_by_auto"] = True
                # 自动认证也走非阻塞：启动线程 + 轮询等待结果
                tid = start_login()
                if tid is None:
                    print("[自动] 已有认证任务在运行，跳过本轮")
                else:
                    # 轮询等待结果（最多 SCRIPT_TIMEOUT + 余量）
                    deadline = time.time() + _C.SCRIPT_TIMEOUT + 10
                    while time.time() < deadline:
                        r = get_task_result(tid)
                        if r is not None:
                            break
                        time.sleep(0.5)
                _auto_state["running_by_auto"] = False
                _auto_state["next_run"] = time.time() + interval
        except Exception as e:
            print(f"[自动] 检查异常: {e}")
        finally:
            time.sleep(AUTO_CHECK_INTERVAL)
