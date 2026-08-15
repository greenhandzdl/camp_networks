# -*- coding: utf-8 -*-
"""
Backend 抽象层

根据运行环境自动选择：
- ModuleBackend：root 设备 + 模块已安装 → 调用模块 WebUI HTTP API（完整体验）
- LocalBackend：无 root 或模块未装 → 直接 import drcom_core 在进程内执行认证

两套 backend 共享同一份 UI 代码，仅数据层不同。
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from typing import Dict, List, Optional, Tuple

import requests

# drcom_core.py 由 build_apk.sh 拷贝到本目录
import drcom_core
from drcom_core import DrComConfig, LoginState


# ---------- 环境检测 ----------

def has_root() -> bool:
    """通过 su 检测 root 权限。"""
    try:
        result = subprocess.run(["su", "-c", "id"],
                                capture_output=True, timeout=3)
        return result.returncode == 0 and b"uid=0" in result.stdout
    except Exception:
        return False


def detect_module() -> Dict:
    """
    检测 Magisk 模块是否已安装，并获取 WebUI 端口和运行状态。
    返回 {installed: bool, version: str, port: int, running: bool}
    """
    info = {"installed": False, "version": "", "port": 8080, "running": False}
    mod_dir = "/data/adb/modules/drcom-wlan-login"

    # 检查模块目录是否存在
    try:
        result = subprocess.run(["su", "-c", f"test -f {mod_dir}/module.prop"],
                                capture_output=True, timeout=3)
        if result.returncode != 0:
            return info
        info["installed"] = True
    except Exception:
        return info

    # 读取 module.prop 获取版本
    try:
        result = subprocess.run(
            ["su", "-c", f"cat {mod_dir}/module.prop"],
            capture_output=True, timeout=3, text=True)
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if line.startswith("version="):
                    info["version"] = line.split("=", 1)[1].strip()
                    break
    except Exception:
        pass

    # 读取 config.env 获取 WebUI 端口
    try:
        result = subprocess.run(
            ["su", "-c", f"cat /data/adb/drcom-wlan-login/config.env"],
            capture_output=True, timeout=3, text=True)
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if line.startswith("WEBUI_PORT="):
                    info["port"] = int(line.split("=", 1)[1].strip())
                    break
    except Exception:
        pass

    # 健康检查
    try:
        resp = requests.get(f"http://127.0.0.1:{info['port']}/", timeout=2)
        info["running"] = resp.status_code == 200
    except Exception:
        pass

    return info


def start_webui_via_module():
    """通过 su 调用模块的 start_webui.sh 启动 WebUI。"""
    try:
        subprocess.Popen(
            ["su", "-c",
             "sh /data/adb/modules/drcom-wlan-login/start_webui.sh"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


# ---------- Backend 接口 ----------

class Backend:
    """统一接口：UI 只与 Backend 交互。"""

    def get_env_info(self) -> Dict:
        """返回环境信息：{mode, has_root, module}"""
        raise NotImplementedError

    def load_config(self) -> Optional[DrComConfig]:
        raise NotImplementedError

    def save_config(self, config: DrComConfig) -> bool:
        raise NotImplementedError

    def login_async(self, on_progress=None) -> Tuple[Optional[int], str]:
        """异步登录，返回 (task_id, error_or_empty)。"""
        raise NotImplementedError

    def get_login_result(self, task_id: int) -> Optional[Dict]:
        """轮询登录结果，未结束返回 None。"""
        raise NotImplementedError

    def logout(self) -> Tuple[bool, str]:
        raise NotImplementedError

    def get_wifi_info(self) -> Dict:
        """返回 {ssid, ip, mac, ipv6}，用于 UI 展示。"""
        raise NotImplementedError

    def get_log(self) -> str:
        raise NotImplementedError

    def clear_log(self):
        raise NotImplementedError


# ---------- LocalBackend（无 root 模式）----------

class LocalBackend(Backend):
    """无 root 或桌面调试：在进程内直接调用 drcom_core。"""

    def __init__(self, config_dir: Optional[str] = None):
        if config_dir is None:
            # Kivy App.user_data_dir 或桌面 ~/.drcom
            try:
                from kivy.app import App
                config_dir = os.path.join(App.get_running_app().user_data_dir, "data")
            except Exception:
                config_dir = os.path.expanduser("~/.drcom")
        os.makedirs(config_dir, exist_ok=True)
        self._config_dir = config_dir
        self._config_path = os.path.join(config_dir, "config.env")
        self._state_path = os.path.join(config_dir, "login_state.json")
        self._log_path = os.path.join(config_dir, "auth.log")
        self._task_id = 0
        self._task_result: Optional[Dict] = None
        self._task_lock = threading.Lock()

    def get_env_info(self) -> Dict:
        return {
            "mode": "local",
            "has_root": has_root(),
            "module": detect_module() if has_root() else {"installed": False},
        }

    def load_config(self) -> Optional[DrComConfig]:
        if not os.path.exists(self._config_path):
            return None
        cfg: Dict[str, str] = {}
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        cfg[k.strip()] = v.strip()
        except OSError:
            return None
        return DrComConfig(
            username=cfg.get("USERNAME", ""),
            password=cfg.get("PASSWORD", ""),
            suffix=cfg.get("SUFFIX", "@cmcc"),
            auth_server=cfg.get("AUTH_SERVER", "10.0.1.5"),
            redirect_server=cfg.get("REDIRECT_SERVER", "1.2.3.4"),
            ipv6=cfg.get("IPV6_ADDRESS", ""),
            debug=cfg.get("DEBUG", "false").lower() in ("true", "1"),
        )

    def save_config(self, config: DrComConfig) -> bool:
        try:
            with open(self._config_path, "w", encoding="utf-8") as f:
                f.write(f"USERNAME={config.username}\n")
                f.write(f"PASSWORD={config.password}\n")
                f.write(f"SUFFIX={config.suffix}\n")
                f.write(f"AUTH_SERVER={config.auth_server}\n")
                f.write(f"REDIRECT_SERVER={config.redirect_server}\n")
                f.write(f"IPV6_ADDRESS={config.ipv6}\n")
                f.write(f"DEBUG={'true' if config.debug else 'false'}\n")
            try:
                os.chmod(self._config_path, 0o600)
            except OSError:
                pass
            return True
        except OSError:
            return False

    def login_async(self, on_progress=None) -> Tuple[Optional[int], str]:
        config = self.load_config()
        if not config or not config.username or not config.password:
            return None, "配置不完整，请先填写账号密码"
        with self._task_lock:
            self._task_id += 1
            tid = self._task_id
            self._task_result = None
        threading.Thread(target=self._do_login, args=(tid, config),
                         daemon=True).start()
        return tid, ""

    def _do_login(self, task_id, config):
        output_lines: List[str] = []

        def log(msg):
            output_lines.append(msg)

        log("正在检测网络状态...")
        if drcom_core.check_internet(config):
            log("外网已连通，无需认证。")
            result = {"ok": True, "output": "\n".join(output_lines)}
            self._save_log(result["output"])
            with self._task_lock:
                self._task_result = result
            return

        log(f"网关 {config.redirect_server} 可达性检查...")
        if not drcom_core.check_gateway(config):
            log(f"网关 {config.redirect_server} 不可达")
            result = {"ok": False, "output": "\n".join(output_lines)}
            self._save_log(result["output"])
            with self._task_lock:
                self._task_result = result
            return

        log("获取认证参数...")
        params = drcom_core.fetch_gateway_params(config)
        if any(p is None for p in params):
            log("获取网关参数失败")
            result = {"ok": False, "output": "\n".join(output_lines)}
            self._save_log(result["output"])
            with self._task_lock:
                self._task_result = result
            return

        host, ip, ac_name, ac_ip, mac = params
        log(f"参数: host={host} ip={ip} mac={mac}")
        log("执行登录...")

        ok, resp = drcom_core.perform_login(config, host, ip, ac_name, ac_ip, mac)
        if not ok:
            log(f"登录请求失败: {resp}")
        else:
            log(f"响应: {resp}")
            ok_parse, msg = drcom_core.parse_login_response(resp)
            log(msg)
            if ok_parse:
                state = LoginState(host=host, username=config.username, mac=mac, ip=ip)
                state.save(self._state_path)
                time.sleep(2)
                if drcom_core.check_internet(config):
                    log("登录成功！外网已连通。")
                else:
                    log("登录完成，但外网仍未连通。")
            ok = ok_parse

        result = {"ok": ok, "output": "\n".join(output_lines)}
        self._save_log(result["output"])
        with self._task_lock:
            self._task_result = result

    def get_login_result(self, task_id: int) -> Optional[Dict]:
        with self._task_lock:
            return self._task_result

    def logout(self) -> Tuple[bool, str]:
        state = LoginState.load(self._state_path)
        if not state or not all([state.host, state.username, state.mac, state.ip]):
            return False, "未找到登录状态"
        ok, resp = drcom_core.perform_logout(state.host, state.username,
                                             state.mac, state.ip)
        msg = resp if ok else f"登出失败: {resp}"
        self._save_log(f"[登出] {msg}")
        return ok, msg

    def get_wifi_info(self) -> Dict:
        # 桌面/无 root 用空值占位（Android 上由 native_net 补全）
        try:
            import native_net
            return native_net.get_wifi_info()
        except Exception:
            return {"ssid": "", "ip": "", "mac": "", "ipv6": ""}

    def get_log(self) -> str:
        try:
            with open(self._log_path, "r", encoding="utf-8") as f:
                return f.read()
        except OSError:
            return ""

    def clear_log(self):
        try:
            with open(self._log_path, "w") as f:
                f.write("")
        except OSError:
            pass

    def _save_log(self, text: str):
        try:
            from datetime import datetime
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(f"[{ts}]\n{text}\n\n")
        except OSError:
            pass


# ---------- ModuleBackend（root + 模块已装）----------

class ModuleBackend(Backend):
    """root + 模块：调用模块 WebUI HTTP API 作为后端。"""

    def __init__(self, port: int):
        self._base = f"http://127.0.0.1:{port}"
        self._module_info = detect_module()

    def get_env_info(self) -> Dict:
        return {
            "mode": "module",
            "has_root": True,
            "module": self._module_info,
        }

    def load_config(self) -> Optional[DrComConfig]:
        try:
            resp = requests.get(f"{self._base}/api/config", timeout=3)
            resp.raise_for_status()
            data = resp.json()
            return DrComConfig(
                username=data.get("username", ""),
                password=data.get("password", ""),
                suffix=data.get("suffix", "@cmcc"),
                auth_server=data.get("auth_server", "10.0.1.5"),
                redirect_server=data.get("redirect_server", "1.2.3.4"),
                ipv6=data.get("ipv6_address", ""),
                debug=data.get("debug", "false") == "true",
            )
        except Exception:
            return None

    def save_config(self, config: DrComConfig) -> bool:
        try:
            resp = requests.post(f"{self._base}/api/save_config", timeout=3, data={
                "username": config.username,
                "password": config.password,
                "suffix": config.suffix,
                "auth_server": config.auth_server,
                "redirect_server": config.redirect_server,
                "ipv6_address": config.ipv6,
                "debug": "true" if config.debug else "false",
            })
            return resp.status_code == 200
        except Exception:
            return False

    def login_async(self, on_progress=None) -> Tuple[Optional[int], str]:
        try:
            resp = requests.get(f"{self._base}/api/run", timeout=3)
            data = resp.json()
            if data.get("error") == "busy":
                return None, "已有任务运行中"
            return data.get("task_id"), ""
        except Exception as e:
            return None, f"请求失败: {e}"

    def get_login_result(self, task_id: int) -> Optional[Dict]:
        try:
            resp = requests.get(f"{self._base}/api/task_result?id={task_id}", timeout=2)
            data = resp.json()
            if not data.get("done"):
                return None
            return {"ok": data.get("ok", False), "output": data.get("output", "")}
        except Exception:
            return None

    def logout(self) -> Tuple[bool, str]:
        try:
            resp = requests.get(f"{self._base}/api/logout", timeout=3)
            data = resp.json()
            return data.get("ok", False), data.get("output", "")
        except Exception as e:
            return False, str(e)

    def get_wifi_info(self) -> Dict:
        try:
            resp = requests.get(f"{self._base}/api/wifi_info", timeout=3)
            return resp.json()
        except Exception:
            return {"ssid": "", "ip": "", "mac": "", "ipv6": ""}

    def get_log(self) -> str:
        try:
            resp = requests.get(f"{self._base}/api/log", timeout=3)
            data = resp.json()
            return data.get("content", "")
        except Exception:
            return ""

    def clear_log(self):
        try:
            requests.get(f"{self._base}/api/clear_log", timeout=3)
        except Exception:
            pass


# ---------- 工厂函数 ----------

def detect_and_create() -> Backend:
    """根据环境自动选择 backend。"""
    # 桌面调试：KIVY_FORCE_LOCAL=1 强制本地模式
    if os.environ.get("KIVY_FORCE_LOCAL") == "1":
        return LocalBackend()

    # Android 环境下检测 root + 模块
    if has_root():
        info = detect_module()
        if info["installed"]:
            if not info["running"]:
                start_webui_via_module()
                time.sleep(2)  # 等待启动
                info = detect_module()
            if info["running"]:
                return ModuleBackend(info["port"])

    # 兜底：本地模式
    return LocalBackend()
