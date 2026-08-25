# -*- coding: utf-8 -*-
"""
Backend 抽象层

根据运行环境自动选择：
- ModuleBackend：root + 模块已装 → 通过 WebUI HTTP API（完整体验）
- LocalBackend：无 root 或模块未装 → 直接调用 drcom_core

权限模型：
- root + 模块：所有配置读写走模块 config.env，登录/登出由模块处理
- 无 root：配置存 APK 私有存储，登录/登出在进程内执行
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import webbrowser
from typing import Dict, List, Optional, Tuple

import requests

import drcom_core
from drcom_core import DrComConfig, LoginState


# ---------- 环境检测（结果缓存，避免重复 subprocess）----------

_ROOT_CACHE: Optional[bool] = None


def has_root() -> bool:
    """检测 root 权限（首次调用后缓存结果）。"""
    global _ROOT_CACHE
    if _ROOT_CACHE is not None:
        return _ROOT_CACHE
    try:
        r = subprocess.run(["su", "-c", "id"], capture_output=True, timeout=3)
        _ROOT_CACHE = r.returncode == 0 and b"uid=0" in r.stdout
    except Exception:
        _ROOT_CACHE = False
    return _ROOT_CACHE


# 模块相关常量
_MOD_DIR = "/data/adb/modules/drcom-wlan-login"
_MOD_CONFIG = "/data/adb/drcom-wlan-login/config.env"


def detect_module() -> Dict:
    """检测 Magisk 模块状态：{installed, version, port, running}"""
    info = {"installed": False, "version": "", "port": 8080, "running": False}
    if not has_root():
        return info

    # 检查 module.prop
    try:
        r = subprocess.run(["su", "-c", f"cat {_MOD_DIR}/module.prop"],
                           capture_output=True, timeout=3, text=True)
        if r.returncode != 0:
            return info
        info["installed"] = True
        for line in r.stdout.splitlines():
            if line.startswith("version="):
                info["version"] = line.split("=", 1)[1].strip()
    except Exception:
        return info

    # 读 config.env 获取端口
    try:
        r = subprocess.run(["su", "-c", f"cat {_MOD_CONFIG}"],
                           capture_output=True, timeout=3, text=True)
        if r.returncode == 0:
            for line in r.stdout.splitlines():
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


def _su_cmd(cmd: str, timeout: int = 3) -> Tuple[bool, str]:
    """执行 su 命令，返回 (success, stdout)。"""
    try:
        r = subprocess.run(["su", "-c", cmd], capture_output=True,
                           timeout=timeout, text=True)
        return r.returncode == 0, r.stdout
    except Exception:
        return False, ""


def start_webui(port: int = 8080):
    """启动模块 WebUI。"""
    _su_cmd(f"sh {_MOD_DIR}/start_webui.sh")


def stop_webui(port: int = 8080):
    """停止模块 WebUI（通过 su 杀进程）。"""
    _su_cmd(f"pkill -f 'python3.*webui.py.*{port}'")


# ---------- Backend 接口 ----------

class Backend:
    """统一接口：UI 只与 Backend 交互。"""

    def get_env_info(self) -> Dict:
        raise NotImplementedError

    def load_config(self) -> Optional[DrComConfig]:
        raise NotImplementedError

    def save_config(self, config: DrComConfig) -> bool:
        raise NotImplementedError

    def login_async(self) -> Tuple[Optional[int], str]:
        """异步登录，返回 (task_id, error_or_empty)。"""
        raise NotImplementedError

    def get_login_result(self, task_id: int) -> Optional[Dict]:
        """轮询登录结果，未结束返回 None。"""
        raise NotImplementedError

    def logout(self) -> Tuple[bool, str]:
        raise NotImplementedError

    def get_wifi_info(self) -> Dict:
        raise NotImplementedError

    def get_log(self) -> str:
        raise NotImplementedError

    def clear_log(self):
        raise NotImplementedError

    def open_webui(self) -> Tuple[bool, str]:
        """打开模块 WebUI 面板。"""
        return False, "不支持"

    def list_accounts(self) -> List[Dict]:
        raise NotImplementedError

    def save_account(self, username: str, password: str, overwrite: bool = False) -> Tuple[bool, str]:
        raise NotImplementedError

    def delete_account(self, index: int) -> Tuple[bool, str]:
        raise NotImplementedError

    def get_channels(self) -> Dict:
        raise NotImplementedError

    def save_channel(self, suffix: str, label: str) -> Tuple[bool, str]:
        raise NotImplementedError

    def delete_channel(self, suffix: str) -> Tuple[bool, str]:
        raise NotImplementedError

    def modify_channel(self, suffix: str, label: str) -> Tuple[bool, str]:
        raise NotImplementedError


# ---------- LocalBackend（无 root / 桌面调试）----------

class LocalBackend(Backend):
    """进程内直接调用 drcom_core。配置存 APK 私有存储。"""

    def __init__(self, config_dir: Optional[str] = None):
        if config_dir is None:
            try:
                from kivy.app import App
                config_dir = os.path.join(
                    App.get_running_app().user_data_dir, "data")
            except Exception:
                config_dir = os.path.expanduser("~/.drcom")
        os.makedirs(config_dir, exist_ok=True)
        self._config_dir = config_dir
        self._config_path = os.path.join(config_dir, "config.env")
        self._state_path = os.path.join(config_dir, "login_state.json")
        self._log_path = os.path.join(config_dir, "auth.log")
        self._accounts_path = os.path.join(config_dir, "accounts.json")
        self._channels_path = os.path.join(config_dir, "channels.json")
        self._task_id = 0
        self._task_result: Optional[Dict] = None
        self._task_lock = threading.Lock()

    def get_env_info(self) -> Dict:
        root = has_root()
        mod = detect_module() if root else {"installed": False}
        return {"mode": "local", "has_root": root, "module": mod}

    # --- 配置读写（APK 私有存储）---

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
        config = DrComConfig(
            username=cfg.get("USERNAME", ""),
            password=cfg.get("PASSWORD", ""),
            suffix=cfg.get("SUFFIX", "@cmcc"),
            auth_server=cfg.get("AUTH_SERVER", "10.0.1.5"),
            redirect_server=cfg.get("REDIRECT_SERVER", "1.2.3.4"),
            ipv6=cfg.get("IPV6_ADDRESS", ""),
            debug=cfg.get("DEBUG", "false").lower() in ("true", "1"),
        )
        config.auto_run = cfg.get("AUTO_RUN", "false").lower() in ("true", "1")
        config.target_essid = cfg.get("TARGET_ESSID", "")
        return config

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
                f.write(f"AUTO_RUN={'true' if getattr(config, 'auto_run', False) else 'false'}\n")
                f.write(f"TARGET_ESSID={getattr(config, 'target_essid', '')}\n")
            try:
                os.chmod(self._config_path, 0o600)
            except OSError:
                pass
            return True
        except OSError:
            return False

    # --- 登录/登出（进程内执行）---

    def login_async(self) -> Tuple[Optional[int], str]:
        config = self.load_config()
        if not config or not config.username or not config.password:
            return None, "请先填写账号密码"
        with self._task_lock:
            self._task_id += 1
            tid = self._task_id
            self._task_result = None
        threading.Thread(target=self._do_login, args=(tid, config),
                         daemon=True).start()
        return tid, ""

    def _do_login(self, task_id, config):
        """复用 drcom_core.login_flow 逻辑。"""
        lines: List[str] = []

        def log(msg):
            lines.append(msg)

        log("检测网络状态...")
        if drcom_core.check_internet(config):
            log("外网已连通，无需认证。")
            self._finish(task_id, True, "\n".join(lines))
            return

        if not drcom_core.check_gateway(config):
            log(f"网关 {config.redirect_server} 不可达")
            self._finish(task_id, False, "\n".join(lines))
            return

        log("获取认证参数...")
        params = drcom_core.fetch_gateway_params(config)
        if any(p is None for p in params):
            log("获取网关参数失败")
            self._finish(task_id, False, "\n".join(lines))
            return

        host, ip, ac_name, ac_ip, mac = params
        log(f"参数: host={host} ip={ip}")
        log("执行登录...")

        ok, resp = drcom_core.perform_login(config, host, ip, ac_name, ac_ip, mac)
        if not ok:
            log(f"登录请求失败: {resp}")
            self._finish(task_id, False, "\n".join(lines))
            return

        ok_parse, msg = drcom_core.parse_login_response(resp)
        log(msg)
        if ok_parse:
            LoginState(host=host, username=config.username, mac=mac,
                       ip=ip).save(self._state_path)
            time.sleep(2)
            if drcom_core.check_internet(config):
                log("外网已连通。")
            else:
                log("登录完成，但外网仍未连通。")
        self._finish(task_id, ok_parse, "\n".join(lines))

    def _finish(self, task_id, ok, output):
        self._save_log(output)
        with self._task_lock:
            self._task_result = {"ok": ok, "output": output}

    def get_login_result(self, task_id: int) -> Optional[Dict]:
        with self._task_lock:
            return self._task_result

    def logout(self) -> Tuple[bool, str]:
        state = LoginState.load(self._state_path)
        if not state or not all([state.host, state.username, state.mac, state.ip]):
            return False, "未找到登录状态"
        ok, resp = drcom_core.perform_logout(
            state.host, state.username, state.mac, state.ip)
        msg = resp if ok else f"登出失败: {resp}"
        self._save_log(f"[登出] {msg}")
        return ok, msg

    # --- 辅助 ---

    def get_wifi_info(self) -> Dict:
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
            open(self._log_path, "w").close()
        except OSError:
            pass

    def open_webui(self) -> Tuple[bool, str]:
        """本地模式下手动启动 WebUI 并打开浏览器。"""
        mod = detect_module()
        if not mod.get("installed"):
            return False, "模块未安装"
        port = mod.get("port", 8080)
        if not mod.get("running"):
            start_webui(port)
            time.sleep(2)
            mod = detect_module()
        if mod.get("running"):
            url = f"http://127.0.0.1:{port}"
            try:
                from jnius import autoclass
                Intent = autoclass('android.content.Intent')
                Uri = autoclass('android.net.Uri')
                activity = autoclass(
                    'org.kivy.android.PythonActivity').mActivity
                activity.startActivity(
                    Intent(Intent.ACTION_VIEW, Uri.parse(url)))
            except Exception:
                webbrowser.open(url)
            return True, url
        return False, "WebUI 启动失败"

    def _save_log(self, text: str):
        try:
            from datetime import datetime
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(f"[{ts}]\n{text}\n\n")
        except OSError:
            pass

    # --- 多账户管理 ---

    def _read_json(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return None

    def _write_json(self, path, data):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except OSError:
            return False

    def list_accounts(self) -> List[Dict]:
        data = self._read_json(self._accounts_path)
        return data if isinstance(data, list) else []

    def save_account(self, username, password, overwrite=False):
        if not username:
            return False, "用户名不能为空"
        accounts = self.list_accounts()
        for i, a in enumerate(accounts):
            if a.get("username") == username:
                if not overwrite:
                    return False, "账号已存在"
                accounts[i] = {"username": username, "password": password}
                self._write_json(self._accounts_path, accounts)
                return True, "覆盖成功"
        accounts.append({"username": username, "password": password})
        self._write_json(self._accounts_path, accounts)
        return True, "保存成功"

    def delete_account(self, index):
        accounts = self.list_accounts()
        if not (0 <= index < len(accounts)):
            return False, "索引无效"
        accounts.pop(index)
        self._write_json(self._accounts_path, accounts)
        return True, "删除成功"

    # --- 渠道管理 ---

    DEFAULT_CHANNELS = {
        "@cmcc": "中国移动", "@unicom": "中国联通",
        "@telecom": "中国电信", "@glgd": "中国广电", "": "校园网",
    }

    def get_channels(self) -> Dict:
        data = self._read_json(self._channels_path)
        if not isinstance(data, dict) or not data:
            defaults = dict(self.DEFAULT_CHANNELS)
            self._write_json(self._channels_path, defaults)
            return defaults
        merged = dict(self.DEFAULT_CHANNELS)
        merged.update(data)
        if set(merged.items()) != set(data.items()):
            self._write_json(self._channels_path, merged)
        return merged

    def save_channel(self, suffix, label):
        if not suffix:
            return False, "后缀不能为空"
        if suffix in self.DEFAULT_CHANNELS:
            return False, "内置渠道不可修改"
        channels = self.get_channels()
        channels[suffix] = label
        self._write_json(self._channels_path, channels)
        return True, "保存成功"

    def delete_channel(self, suffix):
        if suffix in self.DEFAULT_CHANNELS:
            return False, "内置渠道不可删除"
        channels = self.get_channels()
        if suffix not in channels:
            return False, "渠道不存在"
        del channels[suffix]
        self._write_json(self._channels_path, channels)
        return True, "删除成功"

    def modify_channel(self, suffix, label):
        if suffix in self.DEFAULT_CHANNELS:
            return False, "内置渠道不可修改"
        if not label:
            return False, "名称不能为空"
        channels = self.get_channels()
        if suffix not in channels:
            return False, "渠道不存在"
        channels[suffix] = label
        self._write_json(self._channels_path, channels)
        return True, "修改成功"


# ---------- ModuleBackend（root + 模块已装）----------

class ModuleBackend(Backend):
    """通过模块 WebUI HTTP API 作为后端。"""

    def __init__(self, port: int):
        self._base = f"http://127.0.0.1:{port}"
        self._port = port
        self._module_info = detect_module()

    def get_env_info(self) -> Dict:
        return {"mode": "module", "has_root": True, "module": self._module_info}

    # --- 配置读写（通过 WebUI API → 模块 config.env）---

    def load_config(self) -> Optional[DrComConfig]:
        try:
            resp = requests.get(f"{self._base}/api/config", timeout=3)
            resp.raise_for_status()
            d = resp.json()
            config = DrComConfig(
                username=d.get("username", ""),
                password=d.get("password", ""),
                suffix=d.get("suffix", "@cmcc"),
                auth_server=d.get("auth_server", "10.0.1.5"),
                redirect_server=d.get("redirect_server", "1.2.3.4"),
                ipv6=d.get("ipv6_address", ""),
                debug=d.get("debug", "false") == "true",
            )
            config.auto_run = d.get("auto_run", "false") == "true"
            config.target_essid = d.get("target_essid", "")
            return config
        except Exception:
            return None

    def save_config(self, config: DrComConfig) -> bool:
        try:
            # /api/save 只保存基本账号，其他设置需调不同端点
            ok = True
            r = requests.post(f"{self._base}/api/save", timeout=3, data={
                "username": config.username,
                "password": config.password,
                "suffix": config.suffix,
            })
            ok = ok and (r.status_code == 200)
            # 服务器/调试设置（不传 port，保持当前端口不变）
            r2 = requests.post(f"{self._base}/api/save_service", timeout=3, data={
                "auth_server": config.auth_server,
                "redirect_server": config.redirect_server,
                "debug": str(config.debug).lower(),
            })
            ok = ok and (r2.status_code == 200)
            # 自动认证设置
            r3 = requests.post(f"{self._base}/api/save_auto", timeout=3, data={
                "auto_run": str(getattr(config, 'auto_run', False)).lower(),
                "target_essid": getattr(config, 'target_essid', ''),
            })
            ok = ok and (r3.status_code == 200)
            return ok
        except Exception:
            return False

    # --- 登录/登出（通过 WebUI API）---

    def login_async(self) -> Tuple[Optional[int], str]:
        try:
            resp = requests.get(f"{self._base}/api/run", timeout=3)
            d = resp.json()
            if d.get("error") == "busy":
                return None, "已有任务运行中"
            return d.get("task_id"), ""
        except Exception as e:
            return None, f"请求失败: {e}"

    def get_login_result(self, task_id: int) -> Optional[Dict]:
        try:
            resp = requests.get(
                f"{self._base}/api/task_result?id={task_id}", timeout=2)
            d = resp.json()
            if not d.get("done"):
                return None
            return {"ok": d.get("ok", False), "output": d.get("output", "")}
        except Exception:
            return None

    def logout(self) -> Tuple[bool, str]:
        try:
            # /api/logout 是异步的，返回 task_id，需轮询结果
            resp = requests.get(f"{self._base}/api/logout", timeout=3)
            d = resp.json()
            if d.get("error") == "busy":
                return False, "已有任务运行中"
            tid = d.get("task_id")
            if tid is None:
                return False, "登出请求失败"
            for _ in range(20):  # 最多等 10 秒
                time.sleep(0.5)
                r = requests.get(
                    f"{self._base}/api/logout_result?id={tid}", timeout=2)
                rd = r.json()
                if rd.get("done"):
                    return rd.get("ok", False), rd.get("output", "")
            return False, "登出超时"
        except Exception as e:
            return False, str(e)

    # --- 辅助 ---

    def get_wifi_info(self) -> Dict:
        try:
            return requests.get(f"{self._base}/api/network", timeout=3).json()
        except Exception:
            return {"ssid": "", "ip": "", "mac": "", "ipv6": ""}

    def get_log(self) -> str:
        try:
            return requests.get(f"{self._base}/api/log", timeout=3).json().get(
                "content", "")
        except Exception:
            return ""

    def clear_log(self):
        try:
            requests.post(f"{self._base}/api/clear_log", timeout=3)
        except Exception:
            pass

    def open_webui(self) -> Tuple[bool, str]:
        url = f"{self._base}"
        try:
            from jnius import autoclass
            Intent = autoclass('android.content.Intent')
            Uri = autoclass('android.net.Uri')
            activity = autoclass(
                'org.kivy.android.PythonActivity').mActivity
            activity.startActivity(
                Intent(Intent.ACTION_VIEW, Uri.parse(url)))
        except Exception:
            webbrowser.open(url)
        return True, url

    # --- 多账户管理（通过 WebUI API）---

    def list_accounts(self) -> List[Dict]:
        try:
            return requests.get(f"{self._base}/api/accounts", timeout=3).json()
        except Exception:
            return []

    def save_account(self, username, password, overwrite=False):
        try:
            r = requests.post(f"{self._base}/api/save_account", timeout=3, data={
                "username": username, "password": password,
                "overwrite": str(overwrite).lower()})
            d = r.json()
            return d.get("ok", False), d.get("error", "")
        except Exception as e:
            return False, str(e)

    def delete_account(self, index):
        try:
            r = requests.post(f"{self._base}/api/delete_account", timeout=3,
                              data={"index": str(index)})
            d = r.json()
            return d.get("ok", False), d.get("error", "")
        except Exception as e:
            return False, str(e)

    # --- 渠道管理（通过 WebUI API）---

    def get_channels(self) -> Dict:
        try:
            return requests.get(f"{self._base}/api/channels", timeout=3).json()
        except Exception:
            return {}

    def save_channel(self, suffix, label):
        try:
            r = requests.post(f"{self._base}/api/save_channel", timeout=3,
                              data={"suffix": suffix, "label": label})
            d = r.json()
            return d.get("ok", False), d.get("error", "")
        except Exception as e:
            return False, str(e)

    def delete_channel(self, suffix):
        try:
            r = requests.post(f"{self._base}/api/delete_channel", timeout=3,
                              data={"suffix": suffix})
            d = r.json()
            return d.get("ok", False), d.get("error", "")
        except Exception as e:
            return False, str(e)

    def modify_channel(self, suffix, label):
        try:
            r = requests.post(f"{self._base}/api/modify_channel", timeout=3,
                              data={"suffix": suffix, "label": label})
            d = r.json()
            return d.get("ok", False), d.get("error", "")
        except Exception as e:
            return False, str(e)


# ---------- 工厂函数 ----------

def detect_and_create() -> Backend:
    """根据环境自动选择 backend。"""
    if os.environ.get("KIVY_FORCE_LOCAL") == "1":
        return LocalBackend()

    # 尝试 root + 模块模式
    if has_root():
        info = detect_module()
        if info["installed"]:
            if not info["running"]:
                start_webui(info.get("port", 8080))
                time.sleep(2)
                info = detect_module()
            if info["running"]:
                return ModuleBackend(info["port"])

    # 兜底：本地模式
    return LocalBackend()
