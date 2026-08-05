#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import re
import subprocess
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs

try:
    import requests
except ImportError:
    requests = None

# ===================== 路径常量 =====================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MOD_DIR = os.path.dirname(os.path.dirname(os.path.dirname(SCRIPT_DIR)))  # 模块目录
# 配置目录默认使用独立数据目录（刷入新版模块不会丢失）
CONFIG_DIR = os.environ.get("DRCOM_CONFIG_DIR", "/data/adb/drcom-wlan-login")
ENV_PATH = os.path.join(CONFIG_DIR, "config.env")
PROP_PATH = os.path.join(MOD_DIR, "module.prop")
SCRIPT_PATH = os.path.join(SCRIPT_DIR, "wlan_login.py")

# ===================== 行为常量 =====================
DEFAULT_PORT = 38080
DEFAULT_SUFFIX = "@cmcc"
DEFAULT_LOG_FILE = "/data/local/tmp/drcom_webui.log"
DEFAULT_DOWNLOAD_DIR = "/sdcard/Download"   # 更新包下载目录（可在 WebUI 修改）
DEFAULT_AUTO_INTERVAL = 5     # 自动认证间隔（分钟）
DEFAULT_AUTO_DELAY = 5        # 接入目标 WiFi 后延迟秒数再触发第一次认证（等待 DHCP 等）
AUTO_CHECK_INTERVAL = 30      # 自动认证轮询 WiFi 状态周期（秒）
GITHUB_REPO = "greenhandzdl/camp_networks_magisk"
CDN_BASE = "https://cdn.jsdelivr.net/gh"   # jsDelivr CDN（国内访问 GitHub 不稳定，优先走 CDN）
WLAN_IFACE = "wlan0"
SCRIPT_TIMEOUT = 60       # 认证脚本超时（秒）
API_TIMEOUT = 10          # 系统命令/API 超时（秒）
SHUTDOWN_DELAY = 1.5      # 端口变更后关闭延迟（秒）
LOG_TAIL_LINES = 100      # WebUI 查看日志显示行数
UA = "DrCOM-Magisk"

# 所有可配置项统一定义在此（写入 config.env，_ENV_KEYS 定义写入顺序）
_ENV_DEFAULTS = {
    "username": "", "password": "", "suffix": DEFAULT_SUFFIX,
    "debug": "false", "port": str(DEFAULT_PORT),
    "log_file": DEFAULT_LOG_FILE, "download_dir": DEFAULT_DOWNLOAD_DIR,
    "auto_run": "false", "target_essid": "", "auto_interval": str(DEFAULT_AUTO_INTERVAL),
    "auto_delay": str(DEFAULT_AUTO_DELAY),
}
_ENV_KEYS = list(_ENV_DEFAULTS)

# ===================== 全局状态 =====================
_run_lock = threading.Lock()
_server = None
_current_proc = None          # 当前运行中的认证子进程（Popen）
_proc_lock = threading.Lock()
_auto_state = {
    "connected": False,         # 是否连上目标 WiFi
    "connect_time": 0.0,        # 接入目标 WiFi 的时刻
    "next_run": 0.0,            # 下次计划执行的 unix 时间戳（0 表示无计划）
    "running_by_auto": False,   # 当前运行的任务是否由自动认证触发
}


# ===================== 配置读写 =====================
def _parse_env(path):
    """通用 .env 文件解析"""
    cfg = dict(_ENV_DEFAULTS)
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
        for key in _ENV_KEYS:
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


# ===================== 网络信息 =====================
def get_wifi_info():
    """通过 dumpsys 获取当前 WiFi 的 SSID/BSSID"""
    try:
        out = subprocess.run(["dumpsys", "wifi"], capture_output=True, text=True,
                             timeout=API_TIMEOUT).stdout
        m = re.search(r"BSSID:\s*([0-9a-fA-F:]{17})", out)
        bssid = m.group(1) if m else ""
        if bssid.lower() == "02:00:00:00:00:00":  # Android 无权限/未连接时的占位值
            bssid = ""
        m = re.search(r"SSID:\s*(\S+)", out)
        ssid = m.group(1).strip('",') if m else ""
        if ssid.lower() in ("0x", "<unknown", "null") or "unknown" in ssid.lower():
            ssid = ""
        return {"ssid": ssid, "bssid": bssid}
    except Exception:
        return {"ssid": "", "bssid": ""}


def get_ip_addresses():
    """获取 wlan 接口的 IPv4/IPv6 地址"""
    ipv4, ipv6 = [], []
    try:
        out = subprocess.run(["ip", "addr", "show", WLAN_IFACE], capture_output=True,
                             text=True, timeout=API_TIMEOUT).stdout
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("inet "):
                ipv4.append(line.split()[1].split("/")[0])
            elif line.startswith("inet6 "):
                addr = line.split()[1].split("/")[0]
                if not addr.startswith("fe80"):  # 跳过链路本地地址
                    ipv6.append(addr)
    except Exception:
        pass
    return {"ipv4": ipv4, "ipv6": ipv6}


# ===================== 认证执行 =====================
def _exec_login():
    """运行认证脚本，返回 (ok, output)；任务并发时返回 None，可被 _stop_login() 终止"""
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


def _stop_login():
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


# ===================== 自动认证 =====================
def _auto_loop():
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
                r = _exec_login()
                _auto_state["running_by_auto"] = False
                if r is None:
                    print("[自动] 已有认证任务在运行，跳过本轮")
                else:
                    print(f"[自动] 认证{'成功' if r[0] else '失败'}\n{r[1]}")
                _auto_state["next_run"] = time.time() + interval
        except Exception as e:
            print(f"[自动] 检查异常: {e}")


# ===================== 更新检测（CDN 优先，GitHub 直连兜底） =====================
def check_update():
    """通过 update.json 检测更新，返回 (release, err)"""
    if requests is None:
        return None, "requests 库未安装"
    urls = [
        f"{CDN_BASE}/{GITHUB_REPO}@main/update.json",
        f"https://github.com/{GITHUB_REPO}/releases/latest/download/update.json",
    ]
    last_err = ""
    for url in urls:
        try:
            resp = requests.get(url, timeout=API_TIMEOUT, headers={"User-Agent": UA})
            resp.raise_for_status()
            d = resp.json()
            tag = d.get("version", "")
            return {
                "tag": tag,
                "versionCode": int(d.get("versionCode", 0)),
                "html_url": d.get("changelog", ""),
                # CDN 加速分支托管 zip（jsDelivr 不支持 Release 资产直连）
                "zip_url": f"{CDN_BASE}/{GITHUB_REPO}@releases/{tag}.zip",
                "zip_fallback": f"https://github.com/{GITHUB_REPO}/releases/download/{tag}/drcom-wlan-login.zip",
            }, None
        except Exception as e:
            last_err = str(e)
    return None, last_err


# ===================== HTML 模板 =====================
HTML_PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<meta name="theme-color" content="#0f0f13">
<title>Dr.COM 认证</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#0f0f13;--card:#1a1a24;--border:#2a2a3a;--primary:#6c5ce7;--primary-light:#a29bfe;
--success:#00b894;--danger:#e17055;--warn:#fdcb6e;--text:#e0e0e0;--text2:#8888a0;--radius:14px}
html,body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,
"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;font-size:15px;line-height:1.5;
min-height:100vh;-webkit-tap-highlight-color:transparent}
.container{max-width:480px;margin:0 auto;padding:16px 16px 92px}
.header{text-align:center;padding:20px 0 12px}
.header h1{font-size:22px;font-weight:700;background:linear-gradient(135deg,var(--primary-light),var(--primary));
-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.header .ver{font-size:12px;color:var(--text2);margin-top:4px}
.card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);
padding:18px;margin-bottom:14px}
.card-title{font-size:14px;font-weight:600;color:var(--text2);text-transform:uppercase;
letter-spacing:.5px;margin-bottom:14px;display:flex;align-items:center;gap:8px}
.card-title .icon{font-size:18px}
.form-group{margin-bottom:14px}
.form-group label{display:block;font-size:13px;color:var(--text2);margin-bottom:6px;font-weight:500}
.form-group input[type=text],.form-group input[type=password],.form-group input[type=number]{
width:100%;padding:12px 14px;background:var(--bg);border:1px solid var(--border);border-radius:10px;
color:var(--text);font-size:15px;outline:none;transition:border-color .2s}
.form-group input:focus{border-color:var(--primary)}
.toggle-row{display:flex;align-items:center;justify-content:space-between;padding:8px 0}
.toggle-row span{font-size:14px;color:var(--text)}
.toggle{position:relative;width:48px;height:28px;cursor:pointer}
.toggle input{display:none}
.toggle .slider{position:absolute;inset:0;background:var(--border);border-radius:14px;transition:.3s}
.toggle .slider:before{content:"";position:absolute;width:22px;height:22px;left:3px;bottom:3px;
background:#fff;border-radius:50%;transition:.3s}
.toggle input:checked+.slider{background:var(--primary)}
.toggle input:checked+.slider:before{transform:translateX(20px)}
.btn{display:flex;align-items:center;justify-content:center;gap:8px;width:100%;padding:14px;
border:none;border-radius:12px;font-size:15px;font-weight:600;cursor:pointer;transition:all .2s}
.btn:active{transform:scale(.97)}
.btn-primary{background:linear-gradient(135deg,var(--primary),var(--primary-light));color:#fff}
.btn-success{background:linear-gradient(135deg,#00b894,#55efc4);color:#1a1a24}
.btn-outline{background:transparent;border:1px solid var(--border);color:var(--text)}
.btn-warn{background:linear-gradient(135deg,#e17055,#fdcb6e);color:#1a1a24}
.btn:disabled{opacity:.5;pointer-events:none}
.btn+.btn{margin-top:10px}
.status-bar{display:flex;align-items:center;gap:8px;padding:10px 14px;border-radius:10px;
font-size:13px;font-weight:500;margin-bottom:14px}
.status-bar.ok{background:rgba(0,184,148,.12);color:var(--success)}
.status-bar.err{background:rgba(225,112,85,.12);color:var(--danger)}
.status-bar.info{background:rgba(108,92,231,.12);color:var(--primary-light)}
.status-bar.warn{background:rgba(253,203,110,.12);color:var(--warn)}
.output-box{background:var(--bg);border:1px solid var(--border);border-radius:10px;
padding:12px;font-family:"SF Mono",Menlo,Consolas,monospace;font-size:12px;
line-height:1.6;max-height:300px;overflow-y:auto;white-space:pre-wrap;word-break:break-all;
color:var(--text);display:none}
.output-box.show{display:block}
.update-info{font-size:13px;color:var(--text2);line-height:1.6}
.update-info .tag{display:inline-block;background:var(--primary);color:#fff;padding:2px 8px;
border-radius:6px;font-size:12px;font-weight:600}
.update-info a{text-decoration:none}
.spinner{display:inline-block;width:18px;height:18px;border:2px solid transparent;
border-top-color:currentColor;border-radius:50%;animation:spin .6s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.hidden{display:none}
.toast{position:fixed;bottom:84px;left:50%;transform:translateX(-50%) translateY(80px);
background:var(--card);border:1px solid var(--border);padding:12px 24px;border-radius:12px;
font-size:14px;font-weight:500;z-index:999;transition:transform .3s;pointer-events:none}
.toast.show{transform:translateX(-50%) translateY(0)}
.hint{font-size:11px;color:var(--text2);margin-top:8px}
.page{display:none}
.page.show{display:block;animation:fadeIn .25s ease}
@keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
.nav{position:fixed;bottom:0;left:0;right:0;display:flex;background:rgba(26,26,36,.92);
backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);border-top:1px solid var(--border);
padding:6px 4px calc(6px + env(safe-area-inset-bottom));z-index:100}
.nav-item{flex:1;text-align:center;font-size:11px;color:var(--text2);padding:4px 0;cursor:pointer;
border-radius:10px;transition:color .2s}
.nav-item .nicon{font-size:20px;display:block;margin-bottom:1px}
.nav-item.active{color:var(--primary-light)}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>Dr.COM WLAN</h1>
    <div class="ver" id="modVer"></div>
  </div>

  <!-- 状态页 -->
  <div id="page-status" class="page show">
    <div class="card">
      <div class="card-title"><span class="icon">&#128225;</span> 网络状态</div>
      <div class="update-info" id="netInfo">加载中...</div>
      <button class="btn btn-outline" style="margin-top:12px" onclick="loadNet(true)">刷新</button>
    </div>
    <div class="card">
      <div class="card-title"><span class="icon">&#9200;</span> 自动认证状态</div>
      <div class="update-info" id="autoStatus">加载中...</div>
    </div>
    <div class="card">
      <div class="card-title"><span class="icon">&#128230;</span> 模块更新</div>
      <button class="btn btn-outline" id="btnCheck" onclick="checkUpdate()">检查更新</button>
      <div class="update-info hidden" id="updateInfo"></div>
    </div>
    <div class="card">
      <div class="card-title"><span class="icon">&#128196;</span> 运行日志</div>
      <button class="btn btn-outline" onclick="viewLog()">查看日志</button>
      <div class="output-box" id="logOutput"></div>
    </div>
  </div>

  <!-- 认证页 -->
  <div id="page-auth" class="page">
    <div class="card">
      <div class="card-title"><span class="icon">&#128273;</span> 认证配置</div>
      <div class="form-group"><label>账号</label>
        <input type="text" id="username" placeholder="学号/工号" autocomplete="off"></div>
      <div class="form-group"><label>密码</label>
        <input type="password" id="password" placeholder="认证密码"></div>
      <div class="form-group"><label>运营商后缀</label>
        <input type="text" id="suffix" placeholder="@cmcc"></div>
      <div class="toggle-row"><span>调试模式</span>
        <label class="toggle"><input type="checkbox" id="debug"><span class="slider"></span></label></div>
      <div style="margin-top:16px">
        <button class="btn btn-primary" id="btnSave" onclick="saveConfig()">保存配置</button></div>
    </div>
    <div class="card">
      <div class="card-title"><span class="icon">&#9889;</span> 认证操作</div>
      <div id="authStatus"></div>
      <button class="btn btn-success" id="btnRun" onclick="runAuth()">
        <span id="btnRunText">&#9654; 立即认证</span></button>
      <div class="output-box" id="authOutput"></div>
    </div>
  </div>

  <!-- 自动页 -->
  <div id="page-auto" class="page">
    <div class="card">
      <div class="card-title"><span class="icon">&#9200;</span> 自动认证</div>
      <div class="toggle-row"><span>启用自动认证</span>
        <label class="toggle"><input type="checkbox" id="autoRun"><span class="slider"></span></label></div>
      <div class="form-group"><label>目标 WiFi 名称（ESSID）</label>
        <div style="display:flex;gap:8px">
          <input type="text" id="targetEssid" placeholder="校园网 WiFi 名称" style="flex:1">
          <button class="btn btn-outline" style="width:auto;padding:12px 14px" onclick="fillEssid()">获取当前</button>
        </div></div>
      <div class="form-group"><label>运行间隔（分钟）</label>
        <input type="number" id="autoInterval" min="1" inputmode="numeric" placeholder="__INTERVAL__"></div>
      <div class="form-group"><label>接入后首次延迟（秒）<span class="hint" style="display:inline;margin-left:6px">等待 DHCP 获取 IP</span></label>
        <input type="number" id="autoDelay" min="0" inputmode="numeric" placeholder="__DELAY__"></div>
      <button class="btn btn-primary" id="btnSaveAuto" onclick="saveAuto()">保存自动设置</button>
      <div class="hint">需已配置账号密码。接入目标 WiFi 立即触发认证并按间隔重跑，断开 WiFi 自动停止。</div>
    </div>
  </div>

  <!-- 设置页 -->
  <div id="page-settings" class="page">
    <div class="card">
      <div class="card-title"><span class="icon">&#128268;</span> 服务设置</div>
      <div class="form-group"><label>WebUI 端口</label>
        <input type="number" id="port" placeholder="__PORT__" min="1" max="65535" inputmode="numeric"></div>
      <div class="form-group"><label>日志文件路径</label>
        <input type="text" id="logFile" placeholder="__LOGFILE__"></div>
      <div class="form-group"><label>更新包下载目录</label>
        <input type="text" id="downloadDir" placeholder="__DOWNLOAD__"></div>
      <button class="btn btn-warn" id="btnService" onclick="saveService()">保存服务设置</button>
      <div class="hint">修改端口后服务会关闭，通过 Magisk Manager 重启即可；日志路径下次启动生效</div>
    </div>
  </div>
</div>

<nav class="nav">
  <div class="nav-item active" data-tab="status" onclick="showTab('status')"><span class="nicon">&#128225;</span>状态</div>
  <div class="nav-item" data-tab="auth" onclick="showTab('auth')"><span class="nicon">&#128273;</span>认证</div>
  <div class="nav-item" data-tab="auto" onclick="showTab('auto')"><span class="nicon">&#9200;</span>自动</div>
  <div class="nav-item" data-tab="settings" onclick="showTab('settings')"><span class="nicon">&#9881;</span>设置</div>
</nav>
<div class="toast" id="toast"></div>

<script>
const $=id=>document.getElementById(id),DFT_SUFFIX="__SUFFIX__",DFT_PORT="__PORT__",DFT_LOG="__LOGFILE__",DFT_DL="__DOWNLOAD__",DFT_INT="__INTERVAL__",DFT_DELAY="__DELAY__";
let _runBusy=false;
document.addEventListener('DOMContentLoaded',()=>{
  fetch('/api/config').then(r=>r.json()).then(c=>{
    $('username').value=c.username||'';$('password').value=c.password||'';
    $('suffix').value=c.suffix||DFT_SUFFIX;$('debug').checked=c.debug==='true';
    $('port').value=c.port||DFT_PORT;$('logFile').value=c.log_file||DFT_LOG;
    $('downloadDir').value=c.download_dir||DFT_DL;
    $('autoRun').checked=c.auto_run==='true';$('targetEssid').value=c.target_essid||'';
    $('autoInterval').value=c.auto_interval||DFT_INT;
    $('autoDelay').value=c.auto_delay!==undefined?c.auto_delay:DFT_DELAY;
  });
  fetch('/api/prop').then(r=>r.json()).then(p=>{
    $('modVer').textContent=(p.name||'')+' '+(p.version||'');
  });
  loadNet(false);
  pollRunStatus();
  setInterval(pollRunStatus,2000);
});
function toast(m){const t=$('toast');t.textContent=m;t.classList.add('show');
  setTimeout(()=>t.classList.remove('show'),2000)}
function btnLoading(b,t){b.disabled=true;b.innerHTML='<span class="spinner"></span> '+t}
function btnReset(b,t){b.disabled=false;b.textContent=t}
function showTab(t){
  document.querySelectorAll('.page').forEach(p=>p.classList.toggle('show',p.id==='page-'+t));
  document.querySelectorAll('.nav-item').forEach(n=>n.classList.toggle('active',n.dataset.tab===t));
}

function saveConfig(){
  const b=$('btnSave');btnLoading(b,'保存中...');
  fetch('/api/save',{method:'POST',body:new URLSearchParams({
    username:$('username').value,password:$('password').value,
    suffix:$('suffix').value,debug:$('debug').checked?'true':'false'})})
  .then(r=>r.json()).then(d=>toast(d.ok?'配置已保存':'保存失败: '+d.error))
  .catch(()=>toast('网络错误')).finally(()=>btnReset(b,'保存配置'));
}

function runAuth(){
  if(_runBusy){stopRun();return}
  const b=$('btnRun'),t=$('btnRunText'),o=$('authOutput'),s=$('authStatus');
  btnLoading(b,'认证中...');t.innerHTML='<span class="spinner"></span> 认证中...';
  o.className='output-box show';o.textContent='正在执行认证脚本...\n';s.innerHTML='';
  fetch('/api/run').then(r=>r.json()).then(d=>{
    if(d.error==='busy'){toast('已有任务运行中，请先停止');return}
    o.textContent=d.output||'(无输出)';
    s.innerHTML=d.ok?'<div class="status-bar ok">&#10003; 认证完成</div>'
      :'<div class="status-bar err">&#10007; 执行异常</div>';
  }).catch(e=>{o.textContent='请求失败: '+e;
    s.innerHTML='<div class="status-bar err">&#10007; 请求失败</div>';
  }).finally(()=>{
    if(!_runBusy)btnReset(b,'&#9654; 立即认证');
    pollRunStatus();
  });
}

function stopRun(){
  fetch('/api/stop_run',{method:'POST'}).then(r=>r.json()).then(d=>{
    if(d.ok)toast('已终止认证任务');else toast(d.error||'停止失败');
    setTimeout(pollRunStatus,300);
  }).catch(()=>toast('请求失败'));
}

function pollRunStatus(){
  fetch('/api/run_status').then(r=>r.json()).then(d=>{
    _runBusy=d.running;
    // 更新认证按钮状态
    const b=$('btnRun'),t=$('btnRunText');
    if(d.running){
      b.disabled=false;
      b.classList.remove('btn-success');b.classList.add('btn-warn');
      const srcTxt=d.source==='auto'?'(自动)':'(手动)';
      t.innerHTML='&#9632; 停止任务 '+srcTxt;
    }else{
      btnReset(b,'&#9654; 立即认证');
      b.classList.remove('btn-warn');b.classList.add('btn-success');
    }
    // 更新自动认证状态卡片
    const el=$('autoStatus');
    let h='';
    if(!d.auto_connected){
      h='<div>&#128683; 未连接目标 WiFi，自动认证待命中</div>';
    }else if(d.running&&d.source==='auto'){
      h='<div>&#9889; 正在执行自动认证...</div>';
    }else if(d.running&&d.source==='manual'){
      h='<div>&#9881; 手动认证任务运行中</div>';
    }else if(d.has_schedule){
      h='<div>&#9200; 距离下次自动执行: <b>'+d.next_run_in+'</b> 秒</div>';
    }else{
      h='<div>&#10003; 已连接目标 WiFi，自动认证待命中</div>';
    }
    h+='<div style="margin-top:4px;font-size:11px;color:var(--text2)">未连接目标 WiFi 时不会触发自动认证</div>';
    el.innerHTML=h;
  }).catch(()=>{});
}

function saveService(){
  const v=$('port').value.trim(),n=parseInt(v);
  if(!n||n<1||n>65535)return toast('请输入 1-65535 的有效端口号');
  const b=$('btnService');btnLoading(b,'保存中...');
  fetch('/api/save_service',{method:'POST',body:new URLSearchParams({port:v,log_file:$('logFile').value,download_dir:$('downloadDir').value})})
  .then(r=>r.json()).then(d=>{
    if(!d.ok){toast('保存失败: '+(d.error||''));return}
    if(d.port_changed){
      document.body.innerHTML='<div style="text-align:center;padding:60px 20px;color:var(--text)">'
        +'<div style="font-size:48px;margin-bottom:16px">&#9889;</div>'
        +'<div style="font-size:18px;font-weight:600">服务已停止</div>'
        +'<div style="font-size:13px;color:var(--text2);margin-top:8px">新端口: '+n
        +'<br>请通过 Magisk Manager 重新启动 WebUI</div></div>';
    }else toast('服务设置已保存');
  }).catch(()=>toast('网络错误')).finally(()=>btnReset(b,'保存服务设置'));
}

function viewLog(){
  const o=$('logOutput');o.className='output-box show';o.textContent='加载中...';
  fetch('/api/log').then(r=>r.json()).then(d=>{
    o.textContent=(d.content||'(日志为空)');
    o.scrollTop=o.scrollHeight;
  }).catch(()=>{o.textContent='日志加载失败'});
}

function loadNet(manual){
  const el=$('netInfo');
  if(manual)el.innerHTML='加载中...';
  fetch('/api/network').then(r=>r.json()).then(d=>{
    el.innerHTML='<div>WiFi: '+(d.ssid||'未连接')+'</div>'
      +'<div>BSSID: '+(d.bssid||'-')+'</div>'
      +'<div>IPv4: '+((d.ipv4&&d.ipv4.length)?d.ipv4.join(', '):'-')+'</div>'
      +'<div>IPv6: '+((d.ipv6&&d.ipv6.length)?d.ipv6.join(', '):'-')+'</div>';
  }).catch(()=>{el.innerHTML='<div class="status-bar err">获取网络信息失败</div>'});
}

function fillEssid(){
  fetch('/api/network').then(r=>r.json()).then(d=>{
    if(d.ssid){$('targetEssid').value=d.ssid;toast('已填充当前 WiFi 名称')}
    else toast('未连接 WiFi 或无法获取 WiFi 名称');
  }).catch(()=>toast('获取失败'));
}

function saveAuto(){
  const b=$('btnSaveAuto');btnLoading(b,'保存中...');
  fetch('/api/save_auto',{method:'POST',body:new URLSearchParams({
    auto_run:$('autoRun').checked?'true':'false',
    target_essid:$('targetEssid').value,
    auto_interval:$('autoInterval').value,
    auto_delay:$('autoDelay').value})})
  .then(r=>r.json()).then(d=>toast(d.ok?'自动设置已保存':'保存失败: '+(d.error||'')))
  .catch(()=>toast('网络错误')).finally(()=>btnReset(b,'保存自动设置'));
}

function checkUpdate(){
  const b=$('btnCheck'),info=$('updateInfo');
  btnLoading(b,'检查中...');info.className='update-info hidden';
  fetch('/api/check_update').then(r=>r.json()).then(d=>{
    if(d.error){info.innerHTML='<div class="status-bar warn">&#9888; '+d.error+'</div>';
      info.className='update-info';return}
    const rel=d.release,cur=d.current_version||'unknown';let h='';
    if(d.has_update){
      h='<div class="status-bar info">&#127881; 发现新版本 <span class="tag">'+rel.tag+'</span></div>'
       +'<button class="btn btn-warn" onclick="doUpdate()">下载并安装更新</button>'
       +(rel.html_url?'<div class="hint"><a href="'+rel.html_url+'" target="_blank">查看更新日志</a></div>':'');
    }else{h='<div class="status-bar ok">&#10003; 当前已是最新版本 ('+cur+')</div>'}
    info.innerHTML=h;info.className='update-info';
    if(!d.has_update)b.style.display='none';
  }).catch(e=>{info.innerHTML='<div class="status-bar err">检查失败: '+e+'</div>';
    info.className='update-info';
  }).finally(()=>{b.disabled=false;if(b.style.display!=='none')b.textContent='重新检查'});
}

function doUpdate(){
  const info=$('updateInfo');
  info.innerHTML='<div class="status-bar info"><span class="spinner"></span> 正在下载更新...</div>';
  fetch('/api/do_update').then(r=>r.json()).then(d=>{
    const cls=d.ok?'ok':'err',icon=d.ok?'&#10003;':'&#10007;';
    const title=d.ok?'更新完成！请在 Magisk Manager 中重新刷入模块。':'更新失败: '+(d.error||'未知错误');
    info.innerHTML='<div class="status-bar '+cls+'">'+icon+' '+title+'</div>'
      +'<div style="font-size:12px;color:var(--text2);margin-top:8px;white-space:pre-wrap">'+(d.output||'')+'</div>';
  }).catch(e=>{info.innerHTML='<div class="status-bar err">更新请求失败: '+e+'</div>'});
}
</script>
</body>
</html>"""


class WebUIHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _post_params(self):
        length = int(self.headers.get("Content-Length", 0))
        return parse_qs(self.rfile.read(length).decode())

    def _param(self, params, key, default=""):
        return params.get(key, [default])[0].strip()

    # ---------- 路由 ----------
    _GET_ROUTES = {
        "/":              "_serve_html",
        "/api/config":    "_api_config",
        "/api/prop":      "_api_prop",
        "/api/run":       "_api_run",
        "/api/run_status": "_api_run_status",
        "/api/network":   "_api_network",
        "/api/log":       "_api_log",
        "/api/check_update": "_api_check_update",
        "/api/do_update": "_api_do_update",
    }
    _POST_ROUTES = {
        "/api/save":         "_api_save",
        "/api/save_auto":    "_api_save_auto",
        "/api/save_service": "_api_save_service",
        "/api/stop_run":     "_api_stop_run",
    }

    def do_GET(self):
        path = self.path.split("?")[0]
        handler = self._GET_ROUTES.get(path)
        if handler:
            getattr(self, handler)()
        else:
            self.send_error(404)

    def do_POST(self):
        handler = self._POST_ROUTES.get(self.path.split("?")[0])
        if handler:
            getattr(self, handler)()
        else:
            self.send_error(404)

    # ---------- GET 处理 ----------
    def _serve_html(self):
        html = (HTML_PAGE.replace("__SUFFIX__", DEFAULT_SUFFIX)
                .replace("__PORT__", str(DEFAULT_PORT))
                .replace("__LOGFILE__", DEFAULT_LOG_FILE)
                .replace("__DOWNLOAD__", DEFAULT_DOWNLOAD_DIR)
                .replace("__INTERVAL__", str(DEFAULT_AUTO_INTERVAL))
                .replace("__DELAY__", str(DEFAULT_AUTO_DELAY)))
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def _api_config(self):
        self._json(read_env())

    def _api_prop(self):
        self._json(read_module_prop())

    def _api_run(self):
        r = _exec_login()
        if r is None:
            return self._json({"ok": False, "error": "busy", "output": "已有认证任务正在运行"})
        self._json({"ok": r[0], "output": r[1]})

    def _api_run_status(self):
        """返回认证任务状态与自动认证调度状态（供前端轮询）"""
        with _proc_lock:
            running = _current_proc is not None
        now = time.time()
        next_run = _auto_state.get("next_run", 0.0)
        next_in = max(0, int(next_run - now)) if next_run > now else 0
        # 区分任务来源
        if running:
            source = "auto" if _auto_state.get("running_by_auto") else "manual"
        else:
            source = None
        self._json({
            "running": running,
            "source": source,
            "auto_connected": _auto_state.get("connected", False),
            "next_run_in": next_in,          # 0 = 无调度（未连接/未启用）或立即可执行
            "has_schedule": next_run > now,   # 是否有待执行的计划
        })

    def _api_stop_run(self):
        """终止当前运行中的认证任务"""
        stopped = _stop_login()
        self._json({"ok": stopped, "error": "" if stopped else "无正在运行的任务"})

    def _api_network(self):
        self._json({**get_wifi_info(), **get_ip_addresses()})

    def _api_log(self):
        path = read_env().get("log_file", DEFAULT_LOG_FILE)
        try:
            with open(path, "r", errors="replace") as f:
                content = "".join(f.readlines()[-LOG_TAIL_LINES:])
        except OSError as e:
            content = f"无法读取日志: {e}"
        self._json({"path": path, "content": content})

    def _api_check_update(self):
        prop = read_module_prop()
        ver = prop.get("version", "unknown")
        try:
            cur_code = int(prop.get("versionCode", 0))
        except ValueError:
            cur_code = 0
        release, err = check_update()
        if err:
            return self._json({"error": err, "current_version": ver})
        self._json({
            "release": release, "current_version": ver,
            "has_update": release["versionCode"] > cur_code,
        })

    def _api_do_update(self):
        if requests is None:
            return self._json({"ok": False, "error": "requests 库未安装", "output": ""})
        try:
            release, err = check_update()
            if not release:
                return self._json({"ok": False, "error": err or "无法获取更新信息", "output": ""})

            dl_dir = read_env().get("download_dir", DEFAULT_DOWNLOAD_DIR) or DEFAULT_DOWNLOAD_DIR
            os.makedirs(dl_dir, exist_ok=True)
            dl_path = os.path.join(dl_dir, "drcom_update.zip")

            # CDN 下载，失败则回退 GitHub 直连
            last_err, source = "", ""
            for source, url in (("CDN", release["zip_url"]), ("直连", release["zip_fallback"])):
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
                return self._json({"ok": False,
                                   "error": f"下载失败（CDN/直连均不可用）: {last_err}", "output": ""})

            size_kb = os.path.getsize(dl_path) / 1024
            out = f"已下载: drcom-wlan-login.zip ({size_kb:.1f} KB, 来源: {source})\n保存到: {dl_path}\n"
            out += "请在 Magisk Manager 中从本地安装此 zip 文件完成更新。"
            self._json({"ok": True, "output": out})
        except Exception as e:
            self._json({"ok": False, "error": str(e), "output": ""})

    # ---------- POST 处理 ----------
    def _api_save(self):
        p = self._post_params()
        debug = self._param(p, "debug", "false").lower() in ("true", "1")
        write_env(
            username=self._param(p, "username"),
            password=self._param(p, "password"),
            suffix=self._param(p, "suffix", DEFAULT_SUFFIX),
            debug=str(debug).lower(),
        )
        self._json({"ok": True})

    def _api_save_auto(self):
        p = self._post_params()
        auto_run = self._param(p, "auto_run", "false").lower() in ("true", "1")
        try:
            interval = int(self._param(p, "auto_interval", str(DEFAULT_AUTO_INTERVAL)))
            if interval < 1:
                raise ValueError
        except ValueError:
            return self._json({"ok": False, "error": "间隔需为不小于 1 的整数（分钟）"})
        try:
            delay = int(self._param(p, "auto_delay", str(DEFAULT_AUTO_DELAY)))
            if delay < 0:
                raise ValueError
        except ValueError:
            return self._json({"ok": False, "error": "延迟需为非负整数（秒）"})
        write_env(auto_run=str(auto_run).lower(),
                  target_essid=self._param(p, "target_essid"),
                  auto_interval=str(interval),
                  auto_delay=str(delay))
        # 保存后重置调度：如已接入目标 WiFi 则重新按 delay 安排
        if _auto_state["connected"]:
            _auto_state["next_run"] = time.time() + delay
        self._json({"ok": True})

    def _api_save_service(self):
        p = self._post_params()
        try:
            port = int(self._param(p, "port"))
            if not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            return self._json({"ok": False, "error": "端口范围 1-65535"})
        log_file = self._param(p, "log_file", DEFAULT_LOG_FILE)
        download_dir = self._param(p, "download_dir", DEFAULT_DOWNLOAD_DIR)
        port_changed = port != read_port()
        write_env(port=str(port), log_file=log_file, download_dir=download_dir)
        self._json({"ok": True, "port_changed": port_changed})
        if port_changed:
            threading.Timer(SHUTDOWN_DELAY, _shutdown).start()


def _shutdown():
    global _server
    print("端口已更改，WebUI 正在关闭...")
    if _server:
        _server.shutdown()
    os._exit(0)


def main():
    global _server
    threading.Thread(target=_auto_loop, daemon=True).start()
    port = read_port()
    _server = HTTPServer(("0.0.0.0", port), WebUIHandler)
    print(f"WebUI 已启动，请访问 http://127.0.0.1:{port}")
    print("按 Ctrl+C 停止")
    _server.serve_forever()


if __name__ == "__main__":
    main()
