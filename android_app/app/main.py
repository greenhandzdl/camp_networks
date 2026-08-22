# -*- coding: utf-8 -*-
"""
Dr.COM WLAN APK 主入口（Kivy 跨平台）

UI 结构：
- StatusScreen  状态页（网络信息 + 登录/登出按钮 + 结果输出）
- ConfigScreen  配置页（账号/密码/后缀/服务器/调试开关）
- AboutScreen   关于页（版本/环境信息/更新）
"""

import os
import sys
import threading
import time

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.core.text import LabelBase


# ---------- 注册支持中文的默认字体 ----------
def _register_cjk_font():
    """将 Android 系统 CJK 字体注册为 Kivy 默认字体。"""
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

# drcom_core 由 build_apk.sh 拷贝到 app/ 目录
import drcom_core
from drcom_core import DrComConfig

# 版本信息（build_apk.sh 生成，桌面模式用默认值）
try:
    from version import __version__, __version_code__
except ImportError:
    __version__ = "dev"
    __version_code__ = 0


KV = """
#:import rgba kivy.utils.rgba

<MyButton@Button>:
    background_normal: ''
    background_down: ''
    background_color: rgba('#2563EB')
    color: rgba('#FFFFFF')
    bold: True
    font_size: '14sp'
    font_name: 'Roboto'
    on_press: self.background_color = rgba('#1D4ED8')
    on_release: self.background_color = rgba('#2563EB')

<MyLabel@Label>:
    color: rgba('#CBD5E1')
    font_size: '12sp'
    font_name: 'Roboto'

<TitleLabel@Label>:
    color: rgba('#F8FAFC')
    font_size: '18sp'
    bold: True
    font_name: 'Roboto'

<DTextInput@TextInput>:
    font_name: 'Roboto'
    font_size: '13sp'
    size_hint_y: None
    height: 50
    multiline: False
    background_normal: ''
    background_active: ''
    background_color: rgba('#1E293B')
    foreground_color: rgba('#E2E8F0')
    hint_text_color: rgba('#64748B')
    cursor_color: rgba('#E2E8F0')
    padding: [12, 10]

<OutputLabel@Label>:
    size_hint_y: None
    height: self.texture_size[1]
    color: rgba('#94A3B8')
    font_size: '12sp'
    font_name: 'Roboto'
    text_size: self.width, None
    halign: 'left'
    valign: 'top'
    padding: [8, 8]


<StatusScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: 16
        spacing: 10

        TitleLabel:
            text: 'Dr.COM WLAN'
            size_hint_y: None
            height: 36

        MyLabel:
            id: env_info
            text: '环境检测中...'
            size_hint_y: None
            height: 22
            font_size: '13sp'
            color: rgba('#64748B')

        BoxLayout:
            orientation: 'horizontal'
            size_hint_y: None
            height: 24
            spacing: 16
            MyLabel:
                id: ssid_label
                text: 'WiFi: --'
                font_size: '13sp'
            MyLabel:
                id: ip_label
                text: 'IP: --'
                font_size: '13sp'

        BoxLayout:
            orientation: 'horizontal'
            size_hint_y: None
            height: 48
            spacing: 12
            MyButton:
                id: btn_login
                text: '  登录  '
                on_press: root.do_login()
            MyButton:
                id: btn_logout
                text: '  登出  '
                background_color: rgba('#DC2626')
                on_press: root.do_logout()
                on_release: self.background_color = rgba('#DC2626')

        MyButton:
            id: btn_webui
            text: '打开 WebUI 面板'
            size_hint_y: None
            height: 0
            opacity: 0
            background_color: rgba('#059669')
            on_press: root.open_webui()
            on_release: self.background_color = rgba('#059669')

        ScrollView:
            OutputLabel:
                id: output
                text: ''


<ConfigScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: 16
        spacing: 10

        TitleLabel:
            text: '配置'
            size_hint_y: None
            height: 36

        ScrollView:
            BoxLayout:
                orientation: 'vertical'
                spacing: 6
                padding: [0, 4, 0, 4]
                size_hint_y: None
                height: self.minimum_height

                MyLabel:
                    text: '用户名'
                    size_hint_y: None
                    height: 22
                DTextInput:
                    id: username
                    hint_text: '请输入用户名'

                MyLabel:
                    text: '密码'
                    size_hint_y: None
                    height: 22
                DTextInput:
                    id: password
                    hint_text: '请输入密码'
                    password: True

                MyLabel:
                    text: '运营商后缀'
                    size_hint_y: None
                    height: 22
                DTextInput:
                    id: suffix
                    hint_text: '@cmcc'
                    text: '@cmcc'

                MyLabel:
                    text: '认证服务器'
                    size_hint_y: None
                    height: 22
                DTextInput:
                    id: auth_server
                    hint_text: '10.0.1.5'
                    text: '10.0.1.5'

                MyLabel:
                    text: '重定向网关'
                    size_hint_y: None
                    height: 22
                DTextInput:
                    id: redirect_server
                    hint_text: '1.2.3.4'
                    text: '1.2.3.4'

        MyButton:
            text: '保存配置'
            size_hint_y: None
            height: 48
            on_press: root.save()

        MyLabel:
            id: save_status
            text: ''
            size_hint_y: None
            height: 22
            font_size: '13sp'


<AboutScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: 16
        spacing: 8

        TitleLabel:
            text: '关于'
            size_hint_y: None
            height: 36

        MyLabel:
            text: 'Dr.COM WLAN v' + root.version
            size_hint_y: None
            height: 26

        MyLabel:
            id: mode_label
            text: '运行模式: --'
            size_hint_y: None
            height: 24
            font_size: '13sp'

        MyLabel:
            id: module_label
            text: '模块状态: --'
            size_hint_y: None
            height: 24
            font_size: '13sp'

        MyLabel:
            id: update_label
            text: ''
            size_hint_y: None
            height: 24
            font_size: '13sp'

        ScrollView:
            OutputLabel:
                id: log_text
                text: '暂无日志'

        BoxLayout:
            size_hint_y: None
            height: 44
            spacing: 12
            MyButton:
                text: '查看日志'
                on_press: root.refresh_log()
            MyButton:
                text: '清除日志'
                background_color: rgba('#DC2626')
                on_press: root.clear_log()
                on_release: self.background_color = rgba('#DC2626')

        MyButton:
            text: '检查更新'
            size_hint_y: None
            height: 44
            background_color: rgba('#059669')
            on_press: root.check_update()
            on_release: self.background_color = rgba('#059669')
"""

Builder.load_string(KV)


class StatusScreen(Screen):

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
        Clock.schedule_once(
            lambda dt: self._update_ui(mode, ssid, ip, info))

    def _update_ui(self, mode, ssid, ip, info):
        self.ids.env_info.text = f"模式: {mode}"
        self.ids.ssid_label.text = f"WiFi: {ssid}"
        self.ids.ip_label.text = f"IP: {ip}"
        # 本地模式 + root + 模块已装 → 显示打开 WebUI 按钮
        btn = self.ids.btn_webui
        if info["mode"] == "local" and info.get("has_root") \
                and info.get("module", {}).get("installed"):
            btn.height = 44
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
        # 先取消轮询，再调度 UI 更新，避免竞态
        if self._poll_event:
            self._poll_event.cancel()
            self._poll_event = None
        Clock.schedule_once(lambda dt: self._login_done(result.get("ok", False),
                                                       result.get("output", "")))
        return False

    def _login_done(self, ok, output):
        self.ids.btn_login.disabled = False
        self.ids.output.text = output + f"\n\n{'认证成功' if ok else '认证失败'}"
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
        if ok:
            self.ids.output.text = f"WebUI 已打开: {msg}\n请在浏览器中操作。"
        else:
            self.ids.output.text = f"无法打开: {msg}"

    def do_logout(self):
        app = App.get_running_app()
        if not app or not app.backend:
            return
        self.ids.btn_logout.disabled = True
        self.ids.output.text = "正在登出...\n"
        threading.Thread(target=self._do_logout_bg, daemon=True).start()

    def _do_logout_bg(self):
        app = App.get_running_app()
        ok, msg = app.backend.logout()
        Clock.schedule_once(lambda dt: self._logout_done(ok, msg))

    def _logout_done(self, ok, msg):
        self.ids.btn_logout.disabled = False
        self.ids.output.text = msg + f"\n\n{'登出成功' if ok else '登出失败'}"


class ConfigScreen(Screen):

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
            self.ids.username.text = cfg.username
            self.ids.password.text = cfg.password
            self.ids.suffix.text = cfg.suffix
            self.ids.auth_server.text = cfg.auth_server
            self.ids.redirect_server.text = cfg.redirect_server

    def save(self):
        app = App.get_running_app()
        if not app or not app.backend:
            return
        username = self.ids.username.text.strip()
        password = self.ids.password.text
        status = self.ids.save_status
        if not username or not password:
            status.text = '用户名和密码不能为空'
            status.color = (0.86, 0.15, 0.15, 1)
            return
        cfg = DrComConfig(
            username=username,
            password=password,
            suffix=self.ids.suffix.text.strip(),
            auth_server=self.ids.auth_server.text.strip(),
            redirect_server=self.ids.redirect_server.text.strip(),
        )
        status.text = '保存中...'
        status.color = (0.88, 0.91, 0.94, 1)
        threading.Thread(target=self._save_bg, args=(cfg,), daemon=True).start()

    def _save_bg(self, cfg):
        ok = App.get_running_app().backend.save_config(cfg)
        Clock.schedule_once(lambda dt: self._save_done(ok))

    def _save_done(self, ok):
        status = self.ids.save_status
        if ok:
            status.text = '配置已保存'
            status.color = (0.06, 0.72, 0.51, 1)
        else:
            status.text = '保存失败，请重试'
            status.color = (0.86, 0.15, 0.15, 1)


class AboutScreen(Screen):
    version = __version__

    def on_enter(self, *args):
        app = App.get_running_app()
        if not app or not app.backend:
            return
        threading.Thread(target=self._refresh_bg, daemon=True).start()

    def _refresh_bg(self):
        app = App.get_running_app()
        info = app.backend.get_env_info()
        mode = "模块模式" if info["mode"] == "module" else "本地模式"
        mod = info.get("module", {})
        mod_status = f"已安装 ({mod.get('version', '?')})" if mod.get("installed") else "未安装"
        Clock.schedule_once(lambda dt: self._update_ui(mode, mod_status))

    def _update_ui(self, mode, mod_status):
        self.ids.mode_label.text = f"运行模式: {mode}"
        self.ids.module_label.text = f"模块状态: {mod_status}"

    def refresh_log(self):
        app = App.get_running_app()
        if not app or not app.backend:
            return
        threading.Thread(target=self._refresh_log_bg, daemon=True).start()

    def _refresh_log_bg(self):
        log = App.get_running_app().backend.get_log()
        Clock.schedule_once(lambda dt: self._set_log(log))

    def _set_log(self, log):
        self.ids.log_text.text = log or "暂无日志"

    def clear_log(self):
        app = App.get_running_app()
        if app and app.backend:
            app.backend.clear_log()
            self.ids.log_text.text = "日志已清除"

    def check_update(self):
        app = App.get_running_app()
        if not app or not app.backend:
            return
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
        Clock.schedule_once(lambda dt: setattr(self.ids.update_label, 'text', msg))


class DrComApp(App):
    title = "Dr.COM WLAN"

    def build(self):
        from kivy.utils import platform
        if platform != 'android':
            Window.size = (400, 700)
        Window.clearcolor = (0.06, 0.07, 0.11, 1)  # #0F1219

        self.backend = None
        sm = ScreenManager()
        sm.add_widget(StatusScreen(name="status"))
        sm.add_widget(ConfigScreen(name="config"))
        sm.add_widget(AboutScreen(name="about"))

        root = BoxLayout(orientation="vertical")
        root.add_widget(sm)

        # 底部导航栏
        ACTIVE = (0.145, 0.388, 0.922, 1)    # #2563EB
        INACTIVE = (0.09, 0.11, 0.16, 1)     # 同背景色
        nav_btns = {}

        def _on_change(instance, value):
            for name, btn in nav_btns.items():
                active = (name == value)
                btn.background_color = ACTIVE if active else INACTIVE
                btn.color = (1, 1, 1, 1) if active else (0.45, 0.50, 0.58, 1)

        nav = BoxLayout(size_hint_y=None, height=48, spacing=2)
        for label, screen in [("状态", "status"), ("配置", "config"), ("关于", "about")]:
            btn = Button(text=label, size_hint=(1, 1), font_name='Roboto',
                         background_normal='', background_down='',
                         background_color=INACTIVE,
                         color=(0.45, 0.50, 0.58, 1), bold=True, font_size='13sp')
            btn.bind(on_press=lambda inst, s=screen: setattr(sm, "current", s))
            nav_btns[screen] = btn
            nav.add_widget(btn)
        sm.bind(current=_on_change)
        nav_btns["status"].background_color = ACTIVE
        nav_btns["status"].color = (1, 1, 1, 1)
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
        """backend 就绪后刷新状态页。"""
        sm = self.root.children[0] if self.root else None
        if isinstance(sm, ScreenManager) and sm.current == "status":
            for screen in sm.screens:
                if screen.name == "status":
                    screen.refresh_env()
                    break

    def on_stop(self):
        """应用退出时停止 WebUI（模块模式）。"""
        try:
            from backend import ModuleBackend, stop_webui
            if isinstance(self.backend, ModuleBackend):
                stop_webui(self.backend._port)
        except Exception:
            pass


if __name__ == "__main__":
    DrComApp().run()
