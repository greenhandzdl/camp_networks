# -*- coding: utf-8 -*-
"""
Dr.COM WLAN APK 主入口（Kivy 跨平台）

UI 结构（4 屏卡片式布局，对齐 WebUI 设计）：
- StatusScreen  状态仪表板（网络 + 认证操作 + 日志 + 更新）
- AuthScreen    认证配置（账号/密码/后缀 + 账号快捷管理）
- AutoScreen    自动认证（开关 + WiFi + 保存）
- SettingsScreen 设置（网络/调试/账号管理/渠道管理）
"""

import os
import sys
import threading
import time

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.core.text import LabelBase
from kivy.utils import rgba


# ---------- 注册支持中文的默认字体 ----------
def _register_cjk_font():
    candidates = [
        '/system/fonts/NotoSansSC-Regular.otf',
        '/system/fonts/NotoSansSC-Medium.otf',
        '/system/fonts/NotoSansCJK-Regular.otf',
        '/system/fonts/NotoSansCJK-Regular.ttc',
        '/system/fonts/DroidSansFallback.ttf',
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                LabelBase.register('Roboto', fn_regular=path, fn_bold=path)
                from kivy.logger import Logger
                Logger.info(f'App: CJK font registered: {path}')
                return
            except Exception as e:
                from kivy.logger import Logger
                Logger.warning(f'App: Failed to register {path}: {e}')
    from kivy.logger import Logger
    Logger.warning('App: No CJK system font found, Chinese may display as squares')

_register_cjk_font()

import drcom_core
from drcom_core import DrComConfig

try:
    from version import __version__, __version_code__
except ImportError:
    __version__ = "dev"
    __version_code__ = 0


KV = """
#:import rgba kivy.utils.rgba

<Card@BoxLayout>:
    orientation: 'vertical'
    padding: dp(16)
    spacing: dp(10)
    size_hint_y: None
    height: self.minimum_height
    canvas.before:
        Color:
            rgba: rgba('#1A1A24')
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(14)]

<MyButton@Button>:
    background_normal: ''
    background_down: ''
    background_color: rgba('#6C5CE7')
    color: rgba('#FFFFFF')
    bold: True
    font_size: '15sp'
    font_name: 'Roboto'
    on_press: self.background_color = rgba('#5A4BD1')
    on_release: self.background_color = rgba('#6C5CE7')

<MyLabel@Label>:
    color: rgba('#E0E0E0')
    font_size: '13sp'
    font_name: 'Roboto'

<TitleLabel@Label>:
    color: rgba('#A29BFE')
    font_size: '13sp'
    bold: True
    font_name: 'Roboto'
    size_hint_y: None
    height: dp(28)

<DTextInput@TextInput>:
    font_name: 'Roboto'
    font_size: '15sp'
    size_hint_y: None
    height: dp(48)
    multiline: False
    background_normal: ''
    background_active: ''
    background_color: rgba('#0F0F13')
    foreground_color: rgba('#E0E0E0')
    hint_text_color: rgba('#555568')
    cursor_color: rgba('#E0E0E0')
    padding: [dp(12), dp(12)]
    canvas.after:
        Color:
            rgba: rgba('#2A2A3A')
        Line:
            rounded_rectangle: (self.x, self.y, self.width, self.height, dp(8))
            width: dp(1)

<OutputLabel@Label>:
    size_hint_y: None
    height: self.texture_size[1]
    color: rgba('#8888A0')
    font_size: '12sp'
    font_name: 'Roboto'
    text_size: self.width, None
    halign: 'left'
    valign: 'top'
    padding: [dp(8), dp(8)]

<DSwitch@ToggleButton>:
    background_normal: ''
    background_down: ''
    background_color: rgba('#2A2A3A')
    color: rgba('#FFFFFF')
    font_name: 'Roboto'
    font_size: '12sp'
    bold: True
    size_hint: None, None
    size: dp(52), dp(32)
    text: '关'
    on_state: self.text = '开' if self.state == 'down' else '关'; self.background_color = rgba('#6C5CE7') if self.state == 'down' else rgba('#2A2A3A')

<DSpinner@Spinner>:
    background_normal: ''
    background_down: ''
    background_color: rgba('#0F0F13')
    color: rgba('#E0E0E0')
    font_name: 'Roboto'
    font_size: '14sp'
    option_cls: 'MyLabel'
    size_hint_y: None
    height: dp(48)
    canvas.after:
        Color:
            rgba: rgba('#2A2A3A')
        Line:
            rounded_rectangle: (self.x, self.y, self.width, self.height, dp(8))
            width: dp(1)


<StatusScreen>:
    ScrollView:
        BoxLayout:
            orientation: 'vertical'
            padding: dp(16)
            spacing: dp(12)
            size_hint_y: None
            height: self.minimum_height

            Card:
                TitleLabel:
                    text: '网络状态'
                MyLabel:
                    id: env_info
                    text: '环境检测中...'
                    color: rgba('#8888A0')
                BoxLayout:
                    orientation: 'horizontal'
                    size_hint_y: None
                    height: dp(24)
                    spacing: dp(16)
                    MyLabel:
                        id: ssid_label
                        text: 'WiFi: --'
                        color: rgba('#8888A0')
                    MyLabel:
                        id: ip_label
                        text: 'IP: --'
                        color: rgba('#8888A0')
                MyLabel:
                    id: mod_info
                    text: ''
                    color: rgba('#555568')
                    font_size: '12sp'
                    size_hint_y: None
                    height: dp(20)
                MyButton:
                    id: btn_webui
                    text: '打开 WebUI 面板'
                    size_hint_y: None
                    height: 0
                    opacity: 0
                    background_color: rgba('#00B894')
                    on_press: root.open_webui()
                    on_release: self.background_color = rgba('#00B894')

            Card:
                TitleLabel:
                    text: '认证操作'
                MyLabel:
                    id: auth_status
                    text: ''
                    size_hint_y: None
                    height: dp(24)
                    color: rgba('#8888A0')
                BoxLayout:
                    orientation: 'horizontal'
                    size_hint_y: None
                    height: dp(48)
                    spacing: dp(10)
                    MyButton:
                        id: btn_login
                        text: '立即认证'
                        background_color: rgba('#00B894')
                        on_press: root.do_login()
                        on_release: self.background_color = rgba('#00B894')
                    MyButton:
                        id: btn_logout
                        text: '登出'
                        background_color: rgba('#E17055')
                        on_press: root.do_logout()
                        on_release: self.background_color = rgba('#E17055')
                ScrollView:
                    size_hint_y: None
                    height: dp(120)
                    OutputLabel:
                        id: output
                        text: ''

            Card:
                TitleLabel:
                    text: '运行日志'
                ScrollView:
                    size_hint_y: None
                    height: dp(100)
                    OutputLabel:
                        id: log_output
                        text: '点击"查看日志"加载'
                BoxLayout:
                    orientation: 'horizontal'
                    size_hint_y: None
                    height: dp(40)
                    spacing: dp(8)
                    MyButton:
                        text: '查看'
                        font_size: '13sp'
                        background_color: rgba('#2A2A3A')
                        on_press: root.view_log()
                        on_release: self.background_color = rgba('#2A2A3A')
                    MyButton:
                        text: '清理'
                        font_size: '13sp'
                        background_color: rgba('#2A2A3A')
                        on_press: root.clear_log()
                        on_release: self.background_color = rgba('#2A2A3A')

            Card:
                TitleLabel:
                    text: '模块更新'
                MyLabel:
                    id: update_label
                    text: 'Dr.COM WLAN v' + root.version
                    color: rgba('#8888A0')
                    size_hint_y: None
                    height: dp(24)
                MyButton:
                    text: '检查更新'
                    size_hint_y: None
                    height: dp(44)
                    background_color: rgba('#2A2A3A')
                    on_press: root.check_update()
                    on_release: self.background_color = rgba('#2A2A3A')


<AuthScreen>:
    ScrollView:
        BoxLayout:
            orientation: 'vertical'
            padding: dp(16)
            spacing: dp(12)
            size_hint_y: None
            height: self.minimum_height

            Card:
                TitleLabel:
                    text: '认证配置'
                MyLabel:
                    text: '账号'
                    size_hint_y: None
                    height: dp(20)
                    color: rgba('#8888A0')
                    font_size: '12sp'
                DTextInput:
                    id: username
                    hint_text: '学号/工号'
                MyLabel:
                    text: '密码'
                    size_hint_y: None
                    height: dp(20)
                    color: rgba('#8888A0')
                    font_size: '12sp'
                DTextInput:
                    id: password
                    hint_text: '认证密码'
                    password: True
                MyLabel:
                    text: '运营商后缀'
                    size_hint_y: None
                    height: dp(20)
                    color: rgba('#8888A0')
                    font_size: '12sp'
                DSpinner:
                    id: suffix_spinner
                    text: '选择运营商'
                    values: []
                    on_text: root._on_suffix_select(self.text)
                MyButton:
                    text: '保存配置'
                    size_hint_y: None
                    height: dp(48)
                    on_press: root.save_config()

            Card:
                TitleLabel:
                    text: '认证操作'
                MyLabel:
                    id: auth_status
                    text: ''
                    size_hint_y: None
                    height: dp(24)
                    color: rgba('#8888A0')
                BoxLayout:
                    orientation: 'horizontal'
                    size_hint_y: None
                    height: dp(48)
                    spacing: dp(10)
                    MyButton:
                        id: btn_login
                        text: '立即认证'
                        background_color: rgba('#00B894')
                        on_press: root.do_login()
                        on_release: self.background_color = rgba('#00B894')
                    MyButton:
                        id: btn_logout
                        text: '登出'
                        background_color: rgba('#E17055')
                        on_press: root.do_logout()
                        on_release: self.background_color = rgba('#E17055')
                ScrollView:
                    size_hint_y: None
                    height: dp(100)
                    OutputLabel:
                        id: auth_output
                        text: ''

            Card:
                TitleLabel:
                    text: '账号快捷管理'
                DSpinner:
                    id: acct_spinner
                    text: '选择已保存账号'
                    values: []
                    on_text: root._on_account_select(self.text)
                BoxLayout:
                    orientation: 'horizontal'
                    size_hint_y: None
                    height: dp(40)
                    spacing: dp(8)
                    MyButton:
                        text: '保存当前'
                        font_size: '13sp'
                        background_color: rgba('#2A2A3A')
                        on_press: root.save_account()
                        on_release: self.background_color = rgba('#2A2A3A')
                    MyButton:
                        id: btn_del_acct
                        text: '删除选中'
                        font_size: '13sp'
                        background_color: rgba('#2A2A3A')
                        on_press: root.delete_account()
                        on_release: self.background_color = rgba('#2A2A3A')
                MyLabel:
                    id: acct_status
                    text: ''
                    size_hint_y: None
                    height: dp(22)
                    color: rgba('#8888A0')
                    font_size: '12sp'


<AutoScreen>:
    ScrollView:
        BoxLayout:
            orientation: 'vertical'
            padding: dp(16)
            spacing: dp(12)
            size_hint_y: None
            height: self.minimum_height

            Card:
                TitleLabel:
                    text: '自动认证'
                BoxLayout:
                    orientation: 'horizontal'
                    size_hint_y: None
                    height: dp(40)
                    MyLabel:
                        text: '启用自动认证'
                        size_hint_x: 1
                    DSwitch:
                        id: auto_run
                MyLabel:
                    text: '目标 WiFi 名称（ESSID）'
                    size_hint_y: None
                    height: dp(20)
                    color: rgba('#8888A0')
                    font_size: '12sp'
                DTextInput:
                    id: target_essid
                    hint_text: '留空则对所有 WiFi 生效'
                MyButton:
                    text: '保存自动设置'
                    size_hint_y: None
                    height: dp(48)
                    on_press: root.save()
                MyLabel:
                    id: auto_status
                    text: ''
                    size_hint_y: None
                    height: dp(22)
                    color: rgba('#8888A0')
                    font_size: '12sp'
                MyLabel:
                    text: '需已配置账号密码。接入目标 WiFi 立即触发认证并按间隔重跑，断开 WiFi 自动停止。'
                    color: rgba('#555568')
                    font_size: '11sp'
                    size_hint_y: None
                    height: dp(32)
                    text_size: self.width, None
                    halign: 'left'


<SettingsScreen>:
    ScrollView:
        BoxLayout:
            orientation: 'vertical'
            padding: dp(16)
            spacing: dp(12)
            size_hint_y: None
            height: self.minimum_height

            Card:
                TitleLabel:
                    text: '网络设置'
                MyLabel:
                    text: '认证服务器 IP'
                    size_hint_y: None
                    height: dp(20)
                    color: rgba('#8888A0')
                    font_size: '12sp'
                DTextInput:
                    id: auth_server
                    hint_text: '10.0.1.5'
                    text: '10.0.1.5'
                MyLabel:
                    text: '网关重定向地址'
                    size_hint_y: None
                    height: dp(20)
                    color: rgba('#8888A0')
                    font_size: '12sp'
                DTextInput:
                    id: redirect_server
                    hint_text: '1.2.3.4'
                    text: '1.2.3.4'
                BoxLayout:
                    orientation: 'horizontal'
                    size_hint_y: None
                    height: dp(40)
                    MyLabel:
                        text: '调试模式'
                        size_hint_x: 1
                    DSwitch:
                        id: debug_switch
                MyButton:
                    text: '保存网络设置'
                    size_hint_y: None
                    height: dp(48)
                    on_press: root.save_network()
                MyLabel:
                    id: net_status
                    text: ''
                    size_hint_y: None
                    height: dp(22)
                    color: rgba('#8888A0')
                    font_size: '12sp'

            Card:
                TitleLabel:
                    text: '多账户设置'
                BoxLayout:
                    id: accounts_list
                    orientation: 'vertical'
                    spacing: dp(4)
                    size_hint_y: None
                    height: self.minimum_height
                MyLabel:
                    text: '添加 / 编辑账号'
                    size_hint_y: None
                    height: dp(20)
                    color: rgba('#8888A0')
                    font_size: '12sp'
                DTextInput:
                    id: acct_username
                    hint_text: '用户名'
                DTextInput:
                    id: acct_password
                    hint_text: '密码'
                    password: True
                BoxLayout:
                    orientation: 'horizontal'
                    size_hint_y: None
                    height: dp(40)
                    spacing: dp(8)
                    MyButton:
                        text: '保存'
                        font_size: '13sp'
                        background_color: rgba('#2A2A3A')
                        on_press: root.save_account()
                        on_release: self.background_color = rgba('#2A2A3A')
                    MyButton:
                        id: btn_del_acct
                        text: '删除'
                        font_size: '13sp'
                        background_color: rgba('#2A2A3A')
                        on_press: root.delete_account()
                        on_release: self.background_color = rgba('#2A2A3A')
                MyLabel:
                    id: acct_status
                    text: ''
                    size_hint_y: None
                    height: dp(22)
                    color: rgba('#8888A0')
                    font_size: '12sp'

            Card:
                TitleLabel:
                    text: '渠道管理'
                BoxLayout:
                    id: channels_list
                    orientation: 'vertical'
                    spacing: dp(4)
                    size_hint_y: None
                    height: self.minimum_height
                BoxLayout:
                    orientation: 'horizontal'
                    size_hint_y: None
                    height: dp(44)
                    spacing: dp(6)
                    DTextInput:
                        id: ch_suffix
                        hint_text: '后缀'
                        size_hint_x: 0.4
                    DTextInput:
                        id: ch_label
                        hint_text: '显示名'
                        size_hint_x: 0.6
                MyButton:
                    id: ch_btn
                    text: '添加渠道'
                    size_hint_y: None
                    height: dp(40)
                    background_color: rgba('#2A2A3A')
                    on_press: root.save_channel()
                    on_release: self.background_color = rgba('#2A2A3A')
                MyButton:
                    id: ch_cancel_btn
                    text: '取消编辑'
                    size_hint_y: None
                    height: dp(36)
                    opacity: 0
                    disabled: True
                    background_color: rgba('#2A2A3A')
                    on_press: root._cancel_ch_edit()
                    on_release: self.background_color = rgba('#2A2A3A')
                MyLabel:
                    id: ch_status
                    text: ''
                    size_hint_y: None
                    height: dp(22)
                    color: rgba('#8888A0')
                    font_size: '12sp'
"""

Builder.load_string(KV)


# ---------- Screen 类 ----------

class StatusScreen(Screen):

    version = __version__

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._task_id = None
        self._poll_event = None

    def on_enter(self, *args):
        self.refresh_env()

    def refresh_env(self):
        app = App.get_running_app()
        if not app or not app.backend:
            return
        threading.Thread(target=self._refresh_env_bg, daemon=True).start()

    def _refresh_env_bg(self):
        app = App.get_running_app()
        info = app.backend.get_env_info()
        wifi = app.backend.get_wifi_info()
        mode = "模块模式" if info["mode"] == "module" else "本地模式"
        ssid = wifi.get("ssid") or "--"
        ip = wifi.get("ip") or "--"
        mod = info.get("module", {})
        mod_text = f"模块: {'已安装 ' + mod.get('version', '') if mod.get('installed') else '未安装'}"
        Clock.schedule_once(
            lambda dt: self._update_ui(mode, ssid, ip, mod_text, info))

    def _update_ui(self, mode, ssid, ip, mod_text, info):
        self.ids.env_info.text = f"模式: {mode}"
        self.ids.ssid_label.text = f"WiFi: {ssid}"
        self.ids.ip_label.text = f"IP: {ip}"
        self.ids.mod_info.text = mod_text
        btn = self.ids.btn_webui
        if info["mode"] == "local" and info.get("has_root") \
                and info.get("module", {}).get("installed"):
            btn.height = dp(44)
            btn.opacity = 1
        elif info["mode"] == "module":
            btn.height = dp(44)
            btn.opacity = 1
        else:
            btn.height = 0
            btn.opacity = 0

    def do_login(self):
        app = App.get_running_app()
        if not app or not app.backend:
            return
        self.ids.btn_login.disabled = True
        self.ids.output.text = "正在登录...\n"
        threading.Thread(target=self._do_login_bg, daemon=True).start()

    def _do_login_bg(self):
        app = App.get_running_app()
        tid, err = app.backend.login_async()
        if err:
            Clock.schedule_once(lambda dt: self._login_done(False, err))
            return
        self._task_id = tid
        self._poll_event = Clock.schedule_interval(self._poll_login, 0.5)

    def _poll_login(self, dt):
        app = App.get_running_app()
        if self._task_id is None:
            return False
        result = app.backend.get_login_result(self._task_id)
        if result is None:
            return True
        if self._poll_event:
            self._poll_event.cancel()
            self._poll_event = None
        Clock.schedule_once(lambda dt: self._login_done(
            result.get("ok", False), result.get("output", "")))
        return False

    def _login_done(self, ok, output):
        self.ids.btn_login.disabled = False
        self.ids.output.text = output + f"\n\n{'认证成功' if ok else '认证失败'}"
        self.ids.auth_status.text = '认证成功' if ok else '认证失败'
        self.ids.auth_status.color = rgba('#00B894') if ok else rgba('#E17055')
        self.refresh_env()

    def open_webui(self):
        app = App.get_running_app()
        if not app or not app.backend:
            return
        self.ids.output.text = "正在启动 WebUI...\n"
        threading.Thread(target=self._open_webui_bg, daemon=True).start()

    def _open_webui_bg(self):
        app = App.get_running_app()
        ok, msg = app.backend.open_webui()
        Clock.schedule_once(lambda dt: self._webui_done(ok, msg))

    def _webui_done(self, ok, msg):
        self.ids.output.text = f"WebUI 已打开: {msg}" if ok else f"无法打开: {msg}"

    def do_logout(self):
        app = App.get_running_app()
        if not app or not app.backend:
            return
        self.ids.btn_logout.disabled = True
        self.ids.output.text = "正在登出...\n"
        threading.Thread(target=self._do_logout_bg, daemon=True).start()

    def _do_logout_bg(self):
        ok, msg = App.get_running_app().backend.logout()
        Clock.schedule_once(lambda dt: self._logout_done(ok, msg))

    def _logout_done(self, ok, msg):
        self.ids.btn_logout.disabled = False
        self.ids.output.text = msg + f"\n\n{'登出成功' if ok else '登出失败'}"

    def view_log(self):
        app = App.get_running_app()
        if not app or not app.backend:
            return
        threading.Thread(target=self._view_log_bg, daemon=True).start()

    def _view_log_bg(self):
        log = App.get_running_app().backend.get_log()
        Clock.schedule_once(lambda dt: setattr(
            self.ids.log_output, 'text', log or '(日志为空)'))

    def clear_log(self):
        app = App.get_running_app()
        if app and app.backend:
            app.backend.clear_log()
            self.ids.log_output.text = "(日志已清理)"

    def check_update(self):
        self.ids.update_label.text = '检查中...'
        threading.Thread(target=self._check_update_bg, daemon=True).start()

    def _check_update_bg(self):
        try:
            import requests
            resp = requests.get(
                "https://raw.githubusercontent.com/greenhandzdl/"
                "camp_networks_magisk/main/update.json", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            remote_code = int(data.get("versionCode", 0))
            if remote_code > __version_code__:
                msg = f"有新版本: {data.get('version', '')} (当前 {__version__})"
            else:
                msg = f"已是最新 ({__version__})"
        except Exception as e:
            msg = f"检查失败: {e}"
        Clock.schedule_once(lambda dt: setattr(
            self.ids.update_label, 'text', msg))


class AuthScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._accounts = []
        self._channels = {}
        self._task_id = None
        self._poll_event = None

    def on_enter(self, *args):
        app = App.get_running_app()
        if not app or not app.backend:
            return
        threading.Thread(target=self._load_bg, daemon=True).start()

    def _load_bg(self):
        app = App.get_running_app()
        cfg = app.backend.load_config()
        accounts = app.backend.list_accounts()
        channels = app.backend.get_channels()
        Clock.schedule_once(lambda dt: self._fill(cfg, accounts, channels))

    def _fill(self, cfg, accounts, channels):
        # 渠道 → 后缀下拉
        self._channels = channels or {}
        ch_list = ['选择运营商']
        for suffix, label in self._channels.items():
            display = f"{label} ({suffix})" if suffix else f"{label} (校园网)"
            ch_list.append(display)
        self.ids.suffix_spinner.values = ch_list
        # 账号下拉
        self._accounts = accounts or []
        acct_list = ['选择已保存账号'] + [a.get('username', '') for a in self._accounts]
        self.ids.acct_spinner.values = acct_list
        if cfg:
            self.ids.username.text = cfg.username
            self.ids.password.text = cfg.password
            # 选中匹配的渠道
            for i, (suffix, label) in enumerate(self._channels.items()):
                if suffix == cfg.suffix:
                    display = f"{label} ({suffix})" if suffix else f"{label} (校园网)"
                    self.ids.suffix_spinner.text = display
                    break

    def _on_suffix_select(self, text):
        pass  # 由 save_config 时反向查找

    def _on_account_select(self, text):
        if text == '选择已保存账号' or not text:
            return
        for acct in self._accounts:
            if acct.get('username') == text:
                self.ids.username.text = acct.get('username', '')
                self.ids.password.text = acct.get('password', '')
                break

    def _get_selected_suffix(self):
        """从 spinner 显示文本反查 suffix 值。"""
        text = self.ids.suffix_spinner.text
        for suffix, label in self._channels.items():
            display = f"{label} ({suffix})" if suffix else f"{label} (校园网)"
            if display == text:
                return suffix
        return self.ids.suffix_spinner.text

    # --- 保存配置 ---

    def save_config(self):
        app = App.get_running_app()
        if not app or not app.backend:
            return
        username = self.ids.username.text.strip()
        password = self.ids.password.text
        if not username or not password:
            self.ids.auth_status.text = '账号和密码不能为空'
            self.ids.auth_status.color = rgba('#E17055')
            return
        suffix = self._get_selected_suffix()
        cfg = DrComConfig(
            username=username, password=password, suffix=suffix,
            auth_server='10.0.1.5', redirect_server='1.2.3.4')
        threading.Thread(target=self._save_cfg_bg, args=(cfg,), daemon=True).start()
        self.ids.auth_status.text = '保存中...'
        self.ids.auth_status.color = rgba('#A29BFE')

    def _save_cfg_bg(self, cfg):
        ok = App.get_running_app().backend.save_config(cfg)
        Clock.schedule_once(lambda dt: self._save_cfg_done(ok))

    def _save_cfg_done(self, ok):
        if ok:
            self.ids.auth_status.text = '配置已保存'
            self.ids.auth_status.color = rgba('#00B894')
        else:
            self.ids.auth_status.text = '保存失败'
            self.ids.auth_status.color = rgba('#E17055')

    # --- 登录/登出 ---

    def do_login(self):
        app = App.get_running_app()
        if not app or not app.backend:
            return
        self.ids.btn_login.disabled = True
        self.ids.auth_output.text = '正在登录...\n'
        threading.Thread(target=self._do_login_bg, daemon=True).start()

    def _do_login_bg(self):
        app = App.get_running_app()
        tid, err = app.backend.login_async()
        if err:
            Clock.schedule_once(lambda dt: self._login_done(False, err))
            return
        self._task_id = tid
        self._poll_event = Clock.schedule_interval(self._poll_login, 0.5)

    def _poll_login(self, dt):
        if self._task_id is None:
            return False
        result = App.get_running_app().backend.get_login_result(self._task_id)
        if result is None:
            return True
        if self._poll_event:
            self._poll_event.cancel()
            self._poll_event = None
        Clock.schedule_once(lambda dt: self._login_done(
            result.get('ok', False), result.get('output', '')))
        return False

    def _login_done(self, ok, output):
        self.ids.btn_login.disabled = False
        self.ids.auth_output.text = output + f"\n\n{'认证成功' if ok else '认证失败'}"
        self.ids.auth_status.text = '认证成功' if ok else '认证失败'
        self.ids.auth_status.color = rgba('#00B894') if ok else rgba('#E17055')

    def do_logout(self):
        app = App.get_running_app()
        if not app or not app.backend:
            return
        self.ids.btn_logout.disabled = True
        self.ids.auth_output.text = '正在登出...\n'
        threading.Thread(target=self._do_logout_bg, daemon=True).start()

    def _do_logout_bg(self):
        ok, msg = App.get_running_app().backend.logout()
        Clock.schedule_once(lambda dt: self._logout_done(ok, msg))

    def _logout_done(self, ok, msg):
        self.ids.btn_logout.disabled = False
        self.ids.auth_output.text = msg + f"\n\n{'登出成功' if ok else '登出失败'}"

    # --- 账号快捷管理 ---

    def save_account(self):
        app = App.get_running_app()
        if not app or not app.backend:
            return
        username = self.ids.username.text.strip()
        password = self.ids.password.text
        if not username:
            self.ids.acct_status.text = '请输入账号'
            self.ids.acct_status.color = rgba('#E17055')
            return
        exists = any(a.get('username') == username for a in self._accounts)
        threading.Thread(target=self._save_acct_bg,
                         args=(username, password, exists), daemon=True).start()

    def _save_acct_bg(self, username, password, overwrite):
        ok, msg = App.get_running_app().backend.save_account(
            username, password, overwrite)
        Clock.schedule_once(lambda dt: self._save_acct_done(ok, msg))

    def _save_acct_done(self, ok, msg):
        self.ids.acct_status.text = msg
        self.ids.acct_status.color = rgba('#00B894') if ok else rgba('#E17055')
        if ok:
            self.on_enter()

    def delete_account(self):
        app = App.get_running_app()
        if not app or not app.backend:
            return
        text = self.ids.acct_spinner.text
        if text == '选择已保存账号' or not text:
            self.ids.acct_status.text = '请先选择要删除的账号'
            self.ids.acct_status.color = rgba('#E17055')
            return
        for i, a in enumerate(self._accounts):
            if a.get('username') == text:
                threading.Thread(target=self._del_acct_bg,
                                 args=(i,), daemon=True).start()
                return
        self.ids.acct_status.text = '账号未找到'
        self.ids.acct_status.color = rgba('#E17055')

    def _del_acct_bg(self, index):
        ok, msg = App.get_running_app().backend.delete_account(index)
        Clock.schedule_once(lambda dt: self._del_acct_done(ok, msg))

    def _del_acct_done(self, ok, msg):
        self.ids.acct_status.text = msg
        self.ids.acct_status.color = rgba('#00B894') if ok else rgba('#E17055')
        if ok:
            self.on_enter()


class AutoScreen(Screen):

    def on_enter(self, *args):
        app = App.get_running_app()
        if not app or not app.backend:
            return
        threading.Thread(target=self._load_bg, daemon=True).start()

    def _load_bg(self):
        cfg = App.get_running_app().backend.load_config()
        Clock.schedule_once(lambda dt: self._fill(cfg))

    def _fill(self, cfg):
        if cfg:
            self.ids.auto_run.state = 'down' if getattr(cfg, 'auto_run', False) else 'normal'
            self.ids.target_essid.text = getattr(cfg, 'target_essid', '') or ''

    def save(self):
        app = App.get_running_app()
        if not app or not app.backend:
            return
        cfg = app.backend.load_config() or DrComConfig()
        cfg.auto_run = self.ids.auto_run.state == 'down'
        cfg.target_essid = self.ids.target_essid.text.strip()
        threading.Thread(target=self._save_bg, args=(cfg,), daemon=True).start()
        self.ids.auto_status.text = '保存中...'
        self.ids.auto_status.color = rgba('#A29BFE')

    def _save_bg(self, cfg):
        ok = App.get_running_app().backend.save_config(cfg)
        Clock.schedule_once(lambda dt: self._save_done(ok))

    def _save_done(self, ok):
        if ok:
            self.ids.auto_status.text = '自动设置已保存'
            self.ids.auto_status.color = rgba('#00B894')
        else:
            self.ids.auto_status.text = '保存失败'
            self.ids.auto_status.color = rgba('#E17055')



class SettingsScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._accounts = []
        self._selected_acct_idx = None
        self._channels = {}
        self._edit_ch_suffix = None

    def on_enter(self, *args):
        app = App.get_running_app()
        if not app or not app.backend:
            return
        threading.Thread(target=self._load_bg, daemon=True).start()

    def _load_bg(self):
        app = App.get_running_app()
        cfg = app.backend.load_config()
        accounts = app.backend.list_accounts()
        channels = app.backend.get_channels()
        Clock.schedule_once(lambda dt: self._fill(cfg, accounts, channels))

    def _fill(self, cfg, accounts, channels):
        if cfg:
            self.ids.auth_server.text = cfg.auth_server
            self.ids.redirect_server.text = cfg.redirect_server
            self.ids.debug_switch.state = 'down' if cfg.debug else 'normal'
        # 账号列表
        self._accounts = accounts or []
        container = self.ids.accounts_list
        container.clear_widgets()
        if not self._accounts:
            lbl = Label(text='  暂无保存账号', color=rgba('#555568'),
                        font_name='Roboto', font_size='13sp',
                        size_hint_y=None, height=dp(28))
            container.add_widget(lbl)
        else:
            for i, acct in enumerate(self._accounts):
                row = BoxLayout(orientation='horizontal', size_hint_y=None,
                                height=dp(44), spacing=dp(4))
                btn = Button(
                    text=f"  {acct.get('username', '')}",
                    size_hint_x=1, background_normal='', background_down='',
                    background_color=(0.06, 0.06, 0.08, 1),
                    color=(0.88, 0.88, 0.93, 1),
                    font_name='Roboto', font_size='14sp',
                    halign='left', valign='middle')
                btn.bind(on_press=lambda inst, idx=i: self._select_acct(idx))
                row.add_widget(btn)
                del_btn = Button(
                    text='删除', size_hint_x=None, width=dp(56),
                    background_normal='', background_down='',
                    background_color=(0.165, 0.165, 0.227, 1),
                    color=(0.88, 0.44, 0.33, 1),
                    font_name='Roboto', font_size='12sp')
                del_btn.bind(on_press=lambda inst, idx=i: self._quick_del_acct(idx))
                row.add_widget(del_btn)
                container.add_widget(row)
        # 渠道列表
        self._channels = channels or {}
        ch_container = self.ids.channels_list
        ch_container.clear_widgets()
        builtin = {'@cmcc', '@unicom', '@telecom', '@glgd', ''}
        for suffix, label in self._channels.items():
            is_builtin = suffix in builtin
            display = f"{label}  ({suffix or '校园网'})"
            row = BoxLayout(orientation='horizontal', size_hint_y=None,
                            height=dp(40), spacing=dp(4))
            lbl = Label(
                text=f"  {display}", size_hint_x=1,
                color=(0.88, 0.88, 0.93, 1), font_name='Roboto',
                font_size='13sp', halign='left', valign='middle')
            row.add_widget(lbl)
            if is_builtin:
                tag = Label(
                    text='内置', size_hint_x=None, width=dp(44),
                    color=(0.53, 0.53, 0.63, 1), font_name='Roboto',
                    font_size='11sp')
                row.add_widget(tag)
            else:
                # 自定义渠道：点击选中编辑
                edit_btn = Button(
                    text='编辑', size_hint_x=None, width=dp(48),
                    background_normal='', background_down='',
                    background_color=(0.165, 0.165, 0.227, 1),
                    color=(0.42, 0.36, 0.91, 1),
                    font_name='Roboto', font_size='12sp')
                edit_btn.bind(on_press=lambda inst, s=suffix, l=label: self._select_channel(s, l))
                row.add_widget(edit_btn)
                del_btn = Button(
                    text='删除', size_hint_x=None, width=dp(56),
                    background_normal='', background_down='',
                    background_color=(0.165, 0.165, 0.227, 1),
                    color=(0.88, 0.44, 0.33, 1),
                    font_name='Roboto', font_size='12sp')
                del_btn.bind(on_press=lambda inst, s=suffix: self._quick_del_channel(s))
                row.add_widget(del_btn)
            ch_container.add_widget(row)

    def _select_acct(self, index):
        if 0 <= index < len(self._accounts):
            acct = self._accounts[index]
            self.ids.acct_username.text = acct.get('username', '')
            self.ids.acct_password.text = acct.get('password', '')
            self._selected_acct_idx = index
            self.ids.acct_status.text = f"已选择: {acct.get('username', '')}"
            self.ids.acct_status.color = rgba('#A29BFE')

    def _quick_del_acct(self, index):
        threading.Thread(target=self._del_acct_bg,
                         args=(index,), daemon=True).start()

    # --- 网络设置 ---

    def save_network(self):
        app = App.get_running_app()
        if not app or not app.backend:
            return
        cfg = app.backend.load_config() or DrComConfig()
        cfg.auth_server = self.ids.auth_server.text.strip()
        cfg.redirect_server = self.ids.redirect_server.text.strip()
        cfg.debug = self.ids.debug_switch.state == 'down'
        threading.Thread(target=self._save_net_bg, args=(cfg,), daemon=True).start()
        self.ids.net_status.text = '保存中...'
        self.ids.net_status.color = rgba('#A29BFE')

    def _save_net_bg(self, cfg):
        ok = App.get_running_app().backend.save_config(cfg)
        Clock.schedule_once(lambda dt: self._save_net_done(ok))

    def _save_net_done(self, ok):
        if ok:
            self.ids.net_status.text = '网络设置已保存'
            self.ids.net_status.color = rgba('#00B894')
        else:
            self.ids.net_status.text = '保存失败'
            self.ids.net_status.color = rgba('#E17055')

    # --- 账号管理 ---

    def save_account(self):
        app = App.get_running_app()
        if not app or not app.backend:
            return
        username = self.ids.acct_username.text.strip()
        password = self.ids.acct_password.text
        if not username:
            self.ids.acct_status.text = '用户名不能为空'
            self.ids.acct_status.color = rgba('#E17055')
            return
        exists = any(a.get('username') == username for a in self._accounts)
        threading.Thread(target=self._save_acct_bg,
                         args=(username, password, exists), daemon=True).start()

    def _save_acct_bg(self, username, password, overwrite):
        ok, msg = App.get_running_app().backend.save_account(
            username, password, overwrite)
        Clock.schedule_once(lambda dt: self._save_acct_done(ok, msg))

    def _save_acct_done(self, ok, msg):
        self.ids.acct_status.text = msg
        self.ids.acct_status.color = rgba('#00B894') if ok else rgba('#E17055')
        self._selected_acct_idx = None
        if ok:
            self.on_enter()

    def delete_account(self):
        if self._selected_acct_idx is None:
            self.ids.acct_status.text = '请先选择一个账号'
            self.ids.acct_status.color = rgba('#E17055')
            return
        threading.Thread(target=self._del_acct_bg,
                         args=(self._selected_acct_idx,), daemon=True).start()

    def _del_acct_bg(self, index):
        ok, msg = App.get_running_app().backend.delete_account(index)
        Clock.schedule_once(lambda dt: self._del_acct_done(ok, msg))

    def _del_acct_done(self, ok, msg):
        self.ids.acct_status.text = msg
        self.ids.acct_status.color = rgba('#00B894') if ok else rgba('#E17055')
        self._selected_acct_idx = None
        self.ids.acct_username.text = ''
        self.ids.acct_password.text = ''
        if ok:
            self.on_enter()

    # --- 渠道管理 ---

    def _select_channel(self, suffix, label):
        """选中自定义渠道进入编辑模式"""
        self._edit_ch_suffix = suffix
        self.ids.ch_suffix.text = suffix
        self.ids.ch_suffix.readonly = True
        self.ids.ch_label.text = label
        self.ids.ch_btn.text = '修改渠道'
        self.ids.ch_cancel_btn.opacity = 1
        self.ids.ch_cancel_btn.disabled = False
        self.ids.ch_status.text = f'编辑模式: {label}'
        self.ids.ch_status.color = rgba('#A29BFE')

    def _cancel_ch_edit(self):
        """取消编辑，回到新增模式"""
        self._edit_ch_suffix = None
        self.ids.ch_suffix.text = ''
        self.ids.ch_suffix.readonly = False
        self.ids.ch_label.text = ''
        self.ids.ch_btn.text = '添加渠道'
        self.ids.ch_cancel_btn.opacity = 0
        self.ids.ch_cancel_btn.disabled = True
        self.ids.ch_status.text = ''

    def save_channel(self):
        app = App.get_running_app()
        if not app or not app.backend:
            return
        suffix = self.ids.ch_suffix.text.strip()
        label = self.ids.ch_label.text.strip()
        if not suffix or not label:
            self.ids.ch_status.text = '后缀和名称不能为空'
            self.ids.ch_status.color = rgba('#E17055')
            return
        is_edit = self._edit_ch_suffix is not None
        if is_edit:
            threading.Thread(target=self._modify_ch_bg,
                             args=(self._edit_ch_suffix, label), daemon=True).start()
        else:
            threading.Thread(target=self._save_ch_bg,
                             args=(suffix, label), daemon=True).start()

    def _modify_ch_bg(self, suffix, label):
        ok, msg = App.get_running_app().backend.modify_channel(suffix, label)
        Clock.schedule_once(lambda dt: self._save_ch_done(ok, msg))

    def _save_ch_bg(self, suffix, label):
        ok, msg = App.get_running_app().backend.save_channel(suffix, label)
        Clock.schedule_once(lambda dt: self._save_ch_done(ok, msg))

    def _save_ch_done(self, ok, msg):
        self.ids.ch_status.text = msg
        self.ids.ch_status.color = rgba('#00B894') if ok else rgba('#E17055')
        self._cancel_ch_edit()
        if ok:
            self.on_enter()

    def delete_channel(self, suffix):
        threading.Thread(target=self._del_ch_bg,
                         args=(suffix,), daemon=True).start()

    def _quick_del_channel(self, suffix):
        self.delete_channel(suffix)

    def _del_ch_bg(self, suffix):
        ok, msg = App.get_running_app().backend.delete_channel(suffix)
        Clock.schedule_once(lambda dt: self._del_ch_done(ok, msg))

    def _del_ch_done(self, ok, msg):
        self.ids.ch_status.text = msg
        self.ids.ch_status.color = rgba('#00B894') if ok else rgba('#E17055')
        if ok:
            self.on_enter()


class DrComApp(App):
    title = "Dr.COM WLAN"

    def build(self):
        from kivy.utils import platform
        if platform != 'android':
            Window.size = (dp(400), dp(720))
        Window.clearcolor = (0.059, 0.059, 0.075, 1)  # #0F0F13

        self.backend = None
        sm = ScreenManager()
        sm.add_widget(StatusScreen(name="status"))
        sm.add_widget(AuthScreen(name="auth"))
        sm.add_widget(AutoScreen(name="auto"))
        sm.add_widget(SettingsScreen(name="settings"))

        root = BoxLayout(orientation="vertical")
        root.add_widget(sm)

        # 底部导航栏（4 tab，对齐 WebUI）
        ACTIVE = (0.424, 0.361, 0.906, 1)     # #6C5CE7
        INACTIVE = (0.059, 0.059, 0.075, 1)   # 同背景色
        nav_btns = {}

        def _on_change(instance, value):
            for name, btn in nav_btns.items():
                active = (name == value)
                btn.background_color = ACTIVE if active else INACTIVE
                btn.color = (0.635, 0.608, 0.996, 1) if active else (0.533, 0.533, 0.627, 1)

        nav = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(2))
        for label, icon, screen in [
            ("状态", "\u25C9", "status"),
            ("认证", "\u26BF", "auth"),
            ("自动", "\u23F0", "auto"),
            ("设置", "\u2699", "settings"),
        ]:
            btn = Button(
                text=f"{icon}\n{label}", size_hint=(1, 1), font_name='Roboto',
                background_normal='', background_down='',
                background_color=INACTIVE,
                color=(0.533, 0.533, 0.627, 1), bold=True, font_size='11sp',
                halign='center', valign='middle')
            btn.bind(on_press=lambda inst, s=screen: setattr(sm, "current", s))
            nav_btns[screen] = btn
            nav.add_widget(btn)
        sm.bind(current=_on_change)
        nav_btns["status"].background_color = ACTIVE
        nav_btns["status"].color = (0.635, 0.608, 0.996, 1)
        root.add_widget(nav)

        Clock.schedule_once(lambda dt: self._init_backend(), 0.1)
        return root

    def _init_backend(self):
        threading.Thread(target=self._init_backend_bg, daemon=True).start()

    def _init_backend_bg(self):
        try:
            from backend import detect_and_create
            self.backend = detect_and_create()
        except Exception as e:
            from kivy.logger import Logger
            Logger.error(f"Backend init failed: {e}")
        Clock.schedule_once(lambda dt: self._on_backend_ready())

    def _on_backend_ready(self):
        if not self.root:
            return
        for child in self.root.children:
            if isinstance(child, ScreenManager):
                if child.current == "status":
                    for screen in child.screens:
                        if screen.name == "status":
                            screen.refresh_env()
                break

    def on_stop(self):
        try:
            from backend import ModuleBackend, stop_webui
            if isinstance(self.backend, ModuleBackend):
                stop_webui(self.backend._port)
        except Exception:
            pass


if __name__ == "__main__":
    DrComApp().run()
