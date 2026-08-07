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


# ===================== 通用脚本任务执行器 =====================

class ScriptTask:
    """封装脚本后台执行：启动/停止/结果轮询，消除登录/登出间的重复代码"""

    def __init__(self, script_path_attr, label):
        self._script_path_attr = script_path_attr
        self._label = label
        self._run_lock = threading.Lock()
        self._proc_lock = threading.Lock()
        self._task_lock = threading.Lock()
        self._proc = None
        self._task_id = 0
        self._result = None

    @property
    def script_path(self):
        return getattr(_C, self._script_path_attr)

    def start(self, *, is_auto=False, on_done=None):
        """启动任务（非阻塞），返回 task_id 或 None（已有任务运行）"""
        if not self._run_lock.acquire(blocking=False):
            return None
        with self._task_lock:
            self._task_id += 1
            self._result = None
        tid = self._task_id
        threading.Thread(
            target=self._run, args=(tid, is_auto, on_done), daemon=True,
        ).start()
        return tid

    def get_result(self, task_id):
        """获取任务结果，返回 {"ok", "output"} 或 None（未完成/任务不存在）"""
        if task_id != self._task_id:
            return None
        with self._task_lock:
            return self._result

    def stop(self):
        """终止当前运行中的任务"""
        with self._proc_lock:
            p = self._proc
        if p is None:
            return False
        try:
            p.kill()
            return True
        except OSError:
            return False

    def _run(self, task_id, is_auto, on_done):
        """后台线程：运行脚本，结果存入 _result"""
        output, ok = "", False
        try:
            proc = subprocess.Popen(
                [sys.executable, self.script_path],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                env={**os.environ, "DRCOM_CONFIG_DIR": _C.CONFIG_DIR},
            )
            with self._proc_lock:
                self._proc = proc
            try:
                raw, _ = proc.communicate(timeout=_C.SCRIPT_TIMEOUT)
                output = raw.decode(errors="replace").strip() if raw else ""
                ok = proc.returncode == 0
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                except OSError:
                    pass
                raw, _ = proc.communicate()
                captured = raw.decode(errors="replace").strip() if raw else ""
                output = f"{self._label}脚本执行超时（{_C.SCRIPT_TIMEOUT}s）"
                if captured:
                    output += f"\n--- 超时前输出 ---\n{captured}"
        except Exception as e:
            output = f"执行失败: {e}"
        finally:
            if not output:
                output = f"[脚本无输出] returncode={ok}, 请检查 {self.script_path} 是否正常"
            with self._task_lock:
                self._result = {"ok": ok, "output": output}
            _write_log(output)
            if is_auto:
                print(f"[自动] {self._label}{'成功' if ok else '失败'}\n{output}")
            with self._proc_lock:
                self._proc = None
            self._run_lock.release()
            if on_done:
                on_done(ok, output)


# ===================== 任务实例 =====================

login_task = ScriptTask("SCRIPT_PATH", "认证")
logout_task = ScriptTask("LOGOUT_SCRIPT_PATH", "登出")


def start_login():
    """启动认证任务（非阻塞），返回 task_id 或 None"""
    return login_task.start()


def get_task_result(task_id):
    """获取认证任务结果"""
    return login_task.get_result(task_id)


def stop_login():
    """终止当前认证任务"""
    return login_task.stop()


def start_logout():
    """启动登出任务（非阻塞），返回 task_id 或 None"""
    return logout_task.start()


def get_logout_result(task_id):
    """获取登出任务结果"""
    return logout_task.get_result(task_id)


# ===================== 自动认证状态 =====================

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


def _is_auto_configured(cfg):
    """检查自动认证是否已正确配置（账号/密码/目标WiFi齐全）"""
    return bool(
        cfg.get("auto_run") == "true"
        and cfg.get("target_essid", "").strip()
        and cfg.get("username")
        and cfg.get("password")
    )


def get_run_status():
    """返回当前认证任务状态与自动认证调度状态（供 API 使用）"""
    with login_task._proc_lock:
        running = login_task._proc is not None
    now = time.time()
    next_run = _auto_state.get("next_run", 0.0)
    next_in = max(0, int(next_run - now)) if next_run > now else 0
    if running:
        source = "auto" if _auto_state.get("running_by_auto") else "manual"
    else:
        source = None

    cfg = read_env()
    auto_enabled = _is_auto_configured(cfg)
    target = cfg.get("target_essid", "").strip()
    if auto_enabled and not _auto_state.get("connected"):
        try:
            ssid = get_wifi_info().get("ssid", "")
            if ssid and ssid == target:
                return {
                    "running": running, "source": source,
                    "auto_enabled": True, "auto_connected": False,
                    "waiting_first": True, "next_run_in": 0, "has_schedule": False,
                }
        except Exception:
            pass

    return {
        "running": running, "source": source,
        "auto_enabled": auto_enabled,
        "auto_connected": _auto_state.get("connected", False),
        "waiting_first": False,
        "next_run_in": next_in, "has_schedule": next_run > now,
    }


def auto_loop():
    """后台循环：接入目标 ESSID 的 WiFi 延迟 auto_delay 秒后触发首次认证，
    之后按 auto_interval 间隔重跑，断开 WiFi 自动停止"""
    while True:
        try:
            cfg = read_env()
            target = cfg.get("target_essid", "").strip()
            enabled = _is_auto_configured(cfg)
            ssid = get_wifi_info().get("ssid", "")
            connected = enabled and ssid == target

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
                tid = login_task.start(is_auto=True)
                if tid is None:
                    print("[自动] 已有认证任务在运行，跳过本轮")
                else:
                    deadline = time.time() + _C.SCRIPT_TIMEOUT + 10
                    while time.time() < deadline:
                        if login_task.get_result(tid) is not None:
                            break
                        time.sleep(0.5)
                _auto_state["running_by_auto"] = False
                _auto_state["next_run"] = time.time() + interval
        except Exception as e:
            print(f"[自动] 检查异常: {e}")
        finally:
            time.sleep(AUTO_CHECK_INTERVAL)
