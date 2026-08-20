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
# Kivy 默认 Roboto 不含 CJK 字符，Android 系统自带 CJK 字体
# 将系统字体注册为 'Roboto' 使所有控件自动使用
def _register_cjk_font():
    """将 Android 系统 CJK 字体注册为 Kivy 默认字体"""
    candidates = [
        # Android 7+ 思源黑体 (单字体文件，优先)
        '/system/fonts/NotoSansSC-Regular.otf',
        '/system/fonts/NotoSansSC-Medium.otf',
        '/system/fonts/NotoSansCJK-Regular.otf',
        # Android 7+ 思源黑体 (合集文件)
        '/system/fonts/NotoSansCJK-Regular.ttc',
        # Android < 7 后备字体
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
    background_color: rgba('#2563EB')
    color: rgba('#FFFFFF')
    bold: True
    font_size: '16sp'
    font_name: 'Roboto'

<MyLabel@Label>:
    color: rgba('#E2E8F0')
    font_size: '14sp'
    font_name: 'Roboto'

<TitleLabel@Label>:
    color: rgba('#FFFFFF')
    font_size: '20sp'
    bold: True
    font_name: 'Roboto'

<NavButton@Button>:
    background_normal: ''
    background_color: rgba('#1E293B')
    color: rgba('#94A3B8')
    font_size: '14sp'
    font_name: 'Roboto'
    bold: True

<StatusScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: 16
        spacing: 12

        TitleLabel:
            text: 'Dr.COM WLAN'
            size_hint_y: None
            height: 40

        MyLabel:
            id: env_info
            text: '环境检测中...'
            size_hint_y: None
            height: 30

        BoxLayout:
            orientation: 'horizontal'
            size_hint_y: None
            height: 40
            spacing: 8
            MyLabel:
                id: ssid_label
                text: 'SSID: --'
            MyLabel:
                id: ip_label
                text: 'IP: --'

        BoxLayout:
            orientation: 'horizontal'
            size_hint_y: None
            height: 50
            spacing: 12
            MyButton:
                id: btn_login
                text: '登录'
                on_press: root.do_login()
            MyButton:
                id: btn_logout
                text: '登出'
                background_color: rgba('#DC2626')
                on_press: root.do_logout()

        ScrollView:
            Label:
                id: output
                text: ''
                size_hint_y: None
                height: self.texture_size[1]
                color: rgba('#E2E8F0')
                font_size: '13sp'
                font_name: 'Roboto'
                text_size: self.width, None
                halign: 'left'
                valign: 'top'
                padding: [4, 4]


<ConfigScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: 16
        spacing: 12

        TitleLabel:
            text: '配置'
            size_hint_y: None
            height: 40

        ScrollView:
            BoxLayout:
                orientation: 'vertical'
                spacing: 8
                size_hint_y: None
                height: self.minimum_height

                MyLabel:
                    text: '用户名'
                    size_hint_y: None
                    height: 24
                TextInput:
                    id: username
                    hint_text: '请输入用户名'
                    font_name: 'Roboto'
                    size_hint_y: None
                    height: 40
                    multiline: False

                MyLabel:
                    text: '密码'
                    size_hint_y: None
                    height: 24
                TextInput:
                    id: password
                    hint_text: '请输入密码'
                    password: True
                    font_name: 'Roboto'
                    size_hint_y: None
                    height: 40
                    multiline: False

                MyLabel:
                    text: '运营商后缀'
                    size_hint_y: None
                    height: 24
                TextInput:
                    id: suffix
                    hint_text: '@cmcc'
                    text: '@cmcc'
                    font_name: 'Roboto'
                    size_hint_y: None
                    height: 40
                    multiline: False

                MyLabel:
                    text: '认证服务器'
                    size_hint_y: None
                    height: 24
                TextInput:
                    id: auth_server
                    hint_text: '10.0.1.5'
                    text: '10.0.1.5'
                    font_name: 'Roboto'
                    size_hint_y: None
                    height: 40
                    multiline: False

                MyLabel:
                    text: '重定向网关'
                    size_hint_y: None
                    height: 24
                TextInput:
                    id: redirect_server
                    hint_text: '1.2.3.4'
                    text: '1.2.3.4'
                    font_name: 'Roboto'
                    size_hint_y: None
                    height: 40
                    multiline: False

        MyButton:
            text: '保存配置'
            size_hint_y: None
            height: 50
            on_press: root.save()


<AboutScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: 16
        spacing: 12

        TitleLabel:
            text: '关于'
            size_hint_y: None
            height: 40

        MyLabel:
            text: 'Dr.COM WLAN APK v' + root.version
            size_hint_y: None
            height: 30

        MyLabel:
            id: mode_label
            text: '运行模式: --'
            size_hint_y: None
            height: 30

        MyLabel:
            id: module_label
            text: '模块状态: --'
            size_hint_y: None
            height: 30

        MyLabel:
            id: update_label
            text: ''
            size_hint_y: None
            height: 30

        ScrollView:
            Label:
                id: log_text
                text: '暂无日志'
                size_hint_y: None
                height: self.texture_size[1]
                color: rgba('#E2E8F0')
                font_size: '12sp'
                font_name: 'Roboto'
                text_size: self.width, None
                halign: 'left'
                valign: 'top'

        BoxLayout:
            size_hint_y: None
            height: 50
            spacing: 12
            MyButton:
                text: '查看日志'
                on_press: root.refresh_log()
            MyButton:
                text: '清除日志'
                background_color: rgba('#DC2626')
                on_press: root.clear_log()

        MyButton:
            text: '检查更新'
            size_hint_y: None
            height: 50
            background_color: rgba('#059669')
            on_press: root.check_update()
"""


Builder.load_string(KV)


class StatusScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app_ref = None
        self._task_id = None
        self._poll_event = None

    def on_enter(self, *args):
        app = App.get_running_app()
        if app:
            self.app_ref = app
        self.refresh_env()

    def refresh_env(self):
        app = self.app_ref or App.get_running_app()
        if not app or not app.backend:
            return
        threading.Thread(target=self._refresh_env_bg, daemon=True).start()

    def _refresh_env_bg(self):
        app = self.app_ref or App.get_running_app()
        info = app.backend.get_env_info()
        wifi = app.backend.get_wifi_info()
        mode = "模块模式 (root)" if info["mode"] == "module" else "本地模式"
        ssid = wifi.get("ssid") or "--"
        ip = wifi.get("ip") or "--"
        Clock.schedule_once(lambda dt: self._update_ui(mode, ssid, ip), 0)

    def _update_ui(self, mode, ssid, ip):
        self.ids.env_info.text = f"模式: {mode}"
        self.ids.ssid_label.text = f"SSID: {ssid}"
        self.ids.ip_label.text = f"IP: {ip}"

    def do_login(self):
        app = self.app_ref or App.get_running_app()
        if not app or not app.backend:
            return
        self.ids.btn_login.disabled = True
        self.ids.output.text = "正在启动登录...\n"
        threading.Thread(target=self._do_login_bg, daemon=True).start()

    def _do_login_bg(self):
        app = self.app_ref or App.get_running_app()
        tid, err = app.backend.login_async()
        if err:
            Clock.schedule_once(lambda dt: self._login_error(err), 0)
            return
        self._task_id = tid
        self._poll_event = Clock.schedule_interval(self._poll_login, 0.5)

    def _poll_login(self, dt):
        app = self.app_ref or App.get_running_app()
        if self._task_id is None:
            return False
        result = app.backend.get_login_result(self._task_id)
        if result is None:
            return True  # 继续轮询
        Clock.schedule_once(lambda dt: self._login_done(result), 0)
        if self._poll_event:
            self._poll_event.cancel()
        return False

    def _login_done(self, result):
        self.ids.btn_login.disabled = False
        ok = result.get("ok", False)
        output = result.get("output", "")
        self.ids.output.text = output + f"\n\n{'认证成功' if ok else '认证失败'}"
        self.refresh_env()

    def _login_error(self, msg):
        self.ids.btn_login.disabled = False
        self.ids.output.text = f"错误: {msg}"

    def do_logout(self):
        app = self.app_ref or App.get_running_app()
        if not app or not app.backend:
            return
        self.ids.btn_logout.disabled = True
        self.ids.output.text = "正在登出...\n"
        threading.Thread(target=self._do_logout_bg, daemon=True).start()

    def _do_logout_bg(self):
        app = self.app_ref or App.get_running_app()
        ok, msg = app.backend.logout()
        Clock.schedule_once(lambda dt: self._logout_done(ok, msg), 0)

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
        app = App.get_running_app()
        cfg = app.backend.load_config()
        Clock.schedule_once(lambda dt: self._fill(cfg), 0)

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
        cfg = DrComConfig(
            username=self.ids.username.text.strip(),
            password=self.ids.password.text,
            suffix=self.ids.suffix.text.strip(),
            auth_server=self.ids.auth_server.text.strip(),
            redirect_server=self.ids.redirect_server.text.strip(),
        )
        if not cfg.username or not cfg.password:
            return
        threading.Thread(target=self._save_bg, args=(cfg,), daemon=True).start()

    def _save_bg(self, cfg):
        app = App.get_running_app()
        ok = app.backend.save_config(cfg)
        msg = "配置已保存" if ok else "保存失败"
        Clock.schedule_once(lambda dt: self._save_done(msg), 0)

    def _save_done(self, msg):
        # 简单 toast 效果：临时改标题（桌面/Android 都可用）
        from kivy.core.window import Window as W
        # Kivy 内置 toast 不跨平台，简单使用 Logger
        from kivy.logger import Logger
        Logger.info(f"Config: {msg}")


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
        mod_info = info.get("module", {})
        if mod_info.get("installed"):
            mod_status = f"已安装 ({mod_info.get('version', '?')})"
        else:
            mod_status = "未安装"
        Clock.schedule_once(lambda dt: self._update_ui(mode, mod_status), 0)

    def _update_ui(self, mode, mod_status):
        self.ids.mode_label.text = f"运行模式: {mode}"
        self.ids.module_label.text = f"模块状态: {mod_status}"

    def refresh_log(self):
        app = App.get_running_app()
        if not app or not app.backend:
            return
        threading.Thread(target=self._refresh_log_bg, daemon=True).start()

    def _refresh_log_bg(self):
        app = App.get_running_app()
        log = app.backend.get_log()
        Clock.schedule_once(lambda dt: self._set_log(log), 0)

    def _set_log(self, log):
        self.ids.log_text.text = log or "暂无日志"

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
                "camp_networks_magisk/main/update.json",
                timeout=10)
            resp.raise_for_status()
            data = resp.json()
            remote_version = data.get("version", "")
            remote_code = int(data.get("versionCode", 0))
            if remote_code > __version_code__:
                msg = f"有新版本: {remote_version} (当前 {__version__})"
            else:
                msg = f"已是最新 ({__version__})"
        except Exception as e:
            msg = f"检查失败: {e}"
        Clock.schedule_once(lambda dt: self._set_update(msg), 0)

    def _set_update(self, msg):
        self.ids.update_label.text = msg

    def clear_log(self):
        app = App.get_running_app()
        if app and app.backend:
            app.backend.clear_log()
            self.ids.log_text.text = "日志已清除"


class DrComApp(App):
    title = "Dr.COM WLAN"

    def build(self):
        # 窗口大小：仅桌面模式设置固定尺寸，Android 全屏
        from kivy.utils import platform
        if platform != 'android':
            Window.size = (400, 700)
        # 深色背景
        Window.clearcolor = (0.09, 0.11, 0.16, 1)

        # 初始化 backend（可能耗时，放后台）
        self.backend = None
        sm = ScreenManager()
        sm.add_widget(StatusScreen(name="status"))
        sm.add_widget(ConfigScreen(name="config"))
        sm.add_widget(AboutScreen(name="about"))

        # 添加底部导航栏
        root = BoxLayout(orientation="vertical")
        root.add_widget(sm)

        nav = BoxLayout(size_hint_y=None, height=50, spacing=0)
        nav_buttons = {}
        ACTIVE_COLOR = (0.145, 0.388, 0.922, 1)  # #2563EB
        INACTIVE_COLOR = (0.118, 0.161, 0.231, 1)  # #1E293B

        def _on_screen_change(instance, value):
            for name, btn in nav_buttons.items():
                btn.background_color = ACTIVE_COLOR if name == value else INACTIVE_COLOR
                btn.color = (1, 1, 1, 1) if name == value else (0.58, 0.64, 0.72, 1)

        for label, screen in [("状态", "status"), ("配置", "config"), ("关于", "about")]:
            btn = Button(text=label, size_hint=(1, 1), font_name='Roboto',
                         background_normal='', background_color=INACTIVE_COLOR,
                         color=(0.58, 0.64, 0.72, 1), bold=True, font_size='14sp')
            btn.bind(on_press=lambda inst, s=screen: setattr(sm, "current", s))
            nav_buttons[screen] = btn
            nav.add_widget(btn)
        sm.bind(current=_on_screen_change)
        # 默认高亮“状态”页
        nav_buttons["status"].background_color = ACTIVE_COLOR
        nav_buttons["status"].color = (1, 1, 1, 1)
        root.add_widget(nav)

        # 后台初始化 backend
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
            self.backend = None
        Clock.schedule_once(lambda dt: self._on_backend_ready(), 0)

    def _on_backend_ready(self):
        # 触发状态页刷新
        sm = self.root.children[1]  # ScreenManager（第一个添加的 child 在 children[-1]）
        # Kivy children 顺序是添加的反序，最后添加的在 children[0]
        for child in self.root.children:
            if isinstance(child, ScreenManager):
                sm = child
                break
        if sm.current == "status":
            for screen in sm.screens:
                if screen.name == "status":
                    screen.refresh_env()


if __name__ == "__main__":
    DrComApp().run()
