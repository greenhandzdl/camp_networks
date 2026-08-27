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
from kivy.uix.label import Label
from kivy.uix.popup import Popup
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
    on_press: self.background_color = rgba('#5A4BD1'); Clock.schedule_once(lambda dt, b=self, c=rgba('#6C5CE7'): setattr(b, 'background_color', c), 0.15)
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

<ModalSpinner>:
    background_normal: ''
    background_down: ''
    background_color: rgba('#0F0F13')
    color: rgba('#E0E0E0')
    font_name: 'Roboto'
    font_size: '14sp'
    size_hint_y: None
    height: dp(48)
    halign: 'center'
    valign: 'middle'
    on_press: self.background_color = rgba('#1A1A2A'); Clock.schedule_once(lambda dt, b=self, c=rgba('#0F0F13'): setattr(b, 'background_color', c), 0.15)
    on_release: self.background_color = rgba('#0F0F13'); self._open_modal()
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
                MyLabel:
                    id: ssid_label
                    text: 'WiFi: --'
                    color: rgba('#8888A0')
                    size_hint_y: None
                    height: dp(22)
                MyLabel:
                    id: ip_label
                    text: 'IPv4: --'
                    color: rgba('#8888A0')
                    size_hint_y: None
                    height: dp(22)
                MyLabel:
                    id: ipv6_label
                    text: 'IPv6: --'
                    color: rgba('#8888A0')
                    font_size: '11sp'
                    size_hint_y: None
                    height: dp(20)
                MyLabel:
                    id: mod_info
                    text: ''
                    color: rgba('#555568')
                    font_size: '12sp'
                    size_hint_y: None
                    height: dp(20)
                BoxLayout:
                    orientation: 'horizontal'
                    size_hint_y: None
                    height: dp(40)
                    spacing: dp(8)
                    MyButton:
                        text: '刷新网络'
                        font_size: '13sp'
                        background_color: rgba('#2A2A3A')
                        on_press: self.background_color = rgba('#1A1A2A'); Clock.schedule_once(lambda dt, b=self, c=rgba('#2A2A3A'): setattr(b, 'background_color', c), 0.15); root.refresh_env()
                        on_release: self.background_color = rgba('#2A2A3A')
                    MyButton:
                        id: btn_webui
                        text: '打开 WebUI'
                        font_size: '13sp'
                        size_hint_x: 0
                        opacity: 0
                        background_color: rgba('#00B894')
                        on_press: self.background_color = rgba('#009B7D'); Clock.schedule_once(lambda dt, b=self, c=rgba('#00B894'): setattr(b, 'background_color', c), 0.15); root.open_webui()
                        on_release: self.background_color = rgba('#00B894')

            Card:
                TitleLabel:
                    text: '自动认证状态'
                MyLabel:
                    id: auto_status
                    text: '加载中...'
                    color: rgba('#8888A0')
                    size_hint_y: None
                    height: dp(40)
                    text_size: self.width, None
                    halign: 'left'
                    valign: 'top'

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
                        on_press: self.background_color = rgba('#009B7D'); Clock.schedule_once(lambda dt, b=self: setattr(b, 'background_color', rgba('#E17055') if root._task_running else rgba('#00B894')), 0.15); root.do_login()
                        on_release: self.background_color = rgba('#E17055') if root._task_running else rgba('#00B894')
                    MyButton:
                        id: btn_logout
                        text: '登出'
                        background_color: rgba('#E17055')
                        on_press: self.background_color = rgba('#C45D47'); Clock.schedule_once(lambda dt, b=self, c=rgba('#E17055'): setattr(b, 'background_color', c), 0.15); root.do_logout()
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
                        text: '点击“查看日志”加载'
                BoxLayout:
                    orientation: 'horizontal'
                    size_hint_y: None
                    height: dp(40)
                    spacing: dp(8)
                    MyButton:
                        text: '查看'
                        font_size: '13sp'
                        background_color: rgba('#2A2A3A')
                        on_press: self.background_color = rgba('#1A1A2A'); Clock.schedule_once(lambda dt, b=self, c=rgba('#2A2A3A'): setattr(b, 'background_color', c), 0.15); root.view_log()
                        on_release: self.background_color = rgba('#2A2A3A')
                    MyButton:
                        text: '清理'
                        font_size: '13sp'
                        background_color: rgba('#2A2A3A')
                        on_press: self.background_color = rgba('#1A1A2A'); Clock.schedule_once(lambda dt, b=self, c=rgba('#2A2A3A'): setattr(b, 'background_color', c), 0.15); root.clear_log()
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
                    id: btn_check_update
                    text: '检查更新'
                    size_hint_y: None
                    height: dp(44)
                    background_color: rgba('#2A2A3A')
                    on_press: self.background_color = rgba('#1A1A2A'); Clock.schedule_once(lambda dt, b=self, c=rgba('#2A2A3A'): setattr(b, 'background_color', c), 0.15); root.check_update()
                    on_release: self.background_color = rgba('#2A2A3A')
                MyLabel:
                    id: update_info
                    text: ''
                    color: rgba('#8888A0')
                    font_size: '12sp'
                    size_hint_y: None
                    height: dp(20)
                MyButton:
                    id: btn_download
                    text: '下载并安装更新'
                    size_hint_y: None
                    height: 0
                    opacity: 0
                    background_color: rgba('#E17055')
                    on_press: self.background_color = rgba('#C45D47'); Clock.schedule_once(lambda dt, b=self, c=rgba('#E17055'): setattr(b, 'background_color', c), 0.15); root.do_update()
                    on_release: self.background_color = rgba('#E17055')


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
                ModalSpinner:
                    id: suffix_spinner
                    text: '选择运营商'
                    on_text: root._on_suffix_select(self.text)
                MyButton:
                    text: '保存配置'
                    size_hint_y: None
                    height: dp(48)
                    on_press: self.background_color = rgba('#5A4BD1'); Clock.schedule_once(lambda dt, b=self, c=rgba('#6C5CE7'): setattr(b, 'background_color', c), 0.15); root.save_config()
                    on_release: self.background_color = rgba('#6C5CE7')

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
                        on_press: self.background_color = rgba('#009B7D'); Clock.schedule_once(lambda dt, b=self: setattr(b, 'background_color', rgba('#E17055') if root._task_running else rgba('#00B894')), 0.15); root.do_login()
                        on_release: self.background_color = rgba('#E17055') if root._task_running else rgba('#00B894')
                    MyButton:
                        id: btn_logout
                        text: '登出'
                        background_color: rgba('#E17055')
                        on_press: self.background_color = rgba('#C45D47'); Clock.schedule_once(lambda dt, b=self, c=rgba('#E17055'): setattr(b, 'background_color', c), 0.15); root.do_logout()
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
                ModalSpinner:
                    id: acct_spinner
                    text: '选择已保存账号'
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
                        on_press: self.background_color = rgba('#1A1A2A'); Clock.schedule_once(lambda dt, b=self, c=rgba('#2A2A3A'): setattr(b, 'background_color', c), 0.15); root.save_account()
                        on_release: self.background_color = rgba('#2A2A3A')
                    MyButton:
                        id: btn_del_acct
                        text: '删除选中'
                        font_size: '13sp'
                        background_color: rgba('#2A2A3A')
                        on_press: self.background_color = rgba('#1A1A2A'); Clock.schedule_once(lambda dt, b=self, c=rgba('#2A2A3A'): setattr(b, 'background_color', c), 0.15); root.delete_account()
                        on_release: self.background_color = rgba('#2A2A3A')
                    MyButton:
                        text: '还原'
                        font_size: '13sp'
                        background_color: rgba('#2A2A3A')
                        on_press: self.background_color = rgba('#1A1A2A'); Clock.schedule_once(lambda dt, b=self, c=rgba('#2A2A3A'): setattr(b, 'background_color', c), 0.15); root.restore_account()
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
                BoxLayout:
                    orientation: 'horizontal'
                    size_hint_y: None
                    height: dp(48)
                    spacing: dp(6)
                    DTextInput:
                        id: target_essid
                        hint_text: '留空则对所有 WiFi 生效'
                        size_hint_x: 1
                    MyButton:
                        text: '获取当前'
                        size_hint_x: None
                        width: dp(80)
                        font_size: '12sp'
                        background_color: rgba('#2A2A3A')
                        on_press: self.background_color = rgba('#1A1A2A'); Clock.schedule_once(lambda dt, b=self, c=rgba('#2A2A3A'): setattr(b, 'background_color', c), 0.15); root.fill_essid()
                        on_release: self.background_color = rgba('#2A2A3A')
                MyLabel:
                    text: '运行间隔（分钟）'
                    size_hint_y: None
                    height: dp(20)
                    color: rgba('#8888A0')
                    font_size: '12sp'
                DTextInput:
                    id: auto_interval
                    hint_text: '5'
                    input_filter: 'int'
                MyLabel:
                    text: '接入后首次延迟（秒）'
                    size_hint_y: None
                    height: dp(20)
                    color: rgba('#8888A0')
                    font_size: '12sp'
                DTextInput:
                    id: auto_delay
                    hint_text: '5'
                    input_filter: 'int'
                MyButton:
                    text: '保存自动设置'
                    size_hint_y: None
                    height: dp(48)
                    on_press: self.background_color = rgba('#5A4BD1'); Clock.schedule_once(lambda dt, b=self, c=rgba('#6C5CE7'): setattr(b, 'background_color', c), 0.15); root.save()
                    on_release: self.background_color = rgba('#6C5CE7')
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
                    text: '服务设置'
                MyLabel:
                    text: 'WebUI 端口'
                    size_hint_y: None
                    height: dp(20)
                    color: rgba('#8888A0')
                    font_size: '12sp'
                DTextInput:
                    id: port_input
                    hint_text: '38080'
                    input_filter: 'int'
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
                MyLabel:
                    text: '日志文件路径'
                    size_hint_y: None
                    height: dp(20)
                    color: rgba('#8888A0')
                    font_size: '12sp'
                DTextInput:
                    id: log_file_input
                    hint_text: '/data/local/tmp/drcom_webui.log'
                MyLabel:
                    text: '更新包下载目录'
                    size_hint_y: None
                    height: dp(20)
                    color: rgba('#8888A0')
                    font_size: '12sp'
                DTextInput:
                    id: download_dir_input
                    hint_text: '/sdcard/Download'
                MyLabel:
                    text: '更新渠道'
                    size_hint_y: None
                    height: dp(20)
                    color: rgba('#8888A0')
                    font_size: '12sp'
                ModalSpinner:
                    id: update_channel_spinner
                    text: 'GitHub'
                BoxLayout:
                    orientation: 'horizontal'
                    size_hint_y: None
                    height: dp(40)
                    MyLabel:
                        text: '调试模式'
                        size_hint_x: 1
                    DSwitch:
                        id: debug_switch
                BoxLayout:
                    orientation: 'horizontal'
                    size_hint_y: None
                    height: dp(40)
                    MyLabel:
                        text: '开机自动打开面板'
                        size_hint_x: 1
                    DSwitch:
                        id: auto_open_webui_switch
                MyButton:
                    text: '保存服务设置'
                    size_hint_y: None
                    height: dp(48)
                    on_press: self.background_color = rgba('#5A4BD1'); Clock.schedule_once(lambda dt, b=self, c=rgba('#6C5CE7'): setattr(b, 'background_color', c), 0.15); root.save_network()
                    on_release: self.background_color = rgba('#6C5CE7')
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
                        on_press: self.background_color = rgba('#1A1A2A'); Clock.schedule_once(lambda dt, b=self, c=rgba('#2A2A3A'): setattr(b, 'background_color', c), 0.15); root.save_account()
                        on_release: self.background_color = rgba('#2A2A3A')
                    MyButton:
                        id: btn_del_acct
                        text: '删除'
                        font_size: '13sp'
                        background_color: rgba('#2A2A3A')
                        on_press: self.background_color = rgba('#1A1A2A'); Clock.schedule_once(lambda dt, b=self, c=rgba('#2A2A3A'): setattr(b, 'background_color', c), 0.15); root.delete_account()
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
                    on_press: self.background_color = rgba('#1A1A2A'); Clock.schedule_once(lambda dt, b=self, c=rgba('#2A2A3A'): setattr(b, 'background_color', c), 0.15); root.save_channel()
                    on_release: self.background_color = rgba('#2A2A3A')
                MyButton:
                    id: ch_cancel_btn
                    text: '取消编辑'
                    size_hint_y: None
                    height: dp(36)
                    opacity: 0
                    disabled: True
                    background_color: rgba('#2A2A3A')
                    on_press: self.background_color = rgba('#1A1A2A'); Clock.schedule_once(lambda dt, b=self, c=rgba('#2A2A3A'): setattr(b, 'background_color', c), 0.15); root._cancel_ch_edit()
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


class ModalSpinner(Button):
    """Spinner 替代：使用 ModalView (Popup) 显示选项，解决 ScrollView 内触摸失效问题"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._options = {}
        self._popup = None

    def set_options(self, display_list, value_map=None):
        """设置选项列表。

        Args:
            display_list: 显示文本列表
            value_map: {display: value} 映射；若为 None 则 value = display
        """
        self._options = {}
        for d in display_list:
            self._options[d] = value_map[d] if value_map and d in value_map else d

    def _open_modal(self):
        if not self._options:
            return
        content = BoxLayout(orientation='vertical', spacing=dp(2),
                            padding=[0, dp(8), 0, dp(8)])
        sv = ScrollView(size_hint=(1, 1))
        inner = BoxLayout(orientation='vertical', size_hint_y=None,
                          spacing=dp(2))
        inner.bind(minimum_height=inner.setter('height'))
        for display in self._options:
            btn = Button(
                text=display, size_hint_y=None, height=dp(48),
                background_normal='', background_down='',
                background_color=rgba('#1A1A24'),
                color=rgba('#E0E0E0'), font_name='Roboto',
                font_size='14sp')
            btn.bind(on_press=lambda inst: (setattr(inst, 'background_color', rgba('#0F0F13')), Clock.schedule_once(lambda dt, b=inst, c=rgba('#1A1A24'): setattr(b, 'background_color', c), 0.15)),
                     on_release=lambda inst: setattr(inst, 'background_color', rgba('#1A1A24')))
            btn.bind(on_press=lambda inst, d=display: self._select(d))
            inner.add_widget(btn)
        sv.add_widget(inner)
        content.add_widget(sv)
        popup = Popup(
            title='', content=content,
            size_hint=(0.85, 0.6),
            background_color=rgba('#0F0F13'),
            separator_color=rgba('#6C5CE7'),
            auto_dismiss=True)
        popup.title = self.text if self.text else '选择'
        self._popup = popup
        popup.open()

    def _select(self, display):
        value = self._options.get(display, display)
        self.text = str(value)
        if hasattr(self, '_popup') and self._popup:
            self._popup.dismiss()
            self._popup = None


# ---------- Screen 类 ----------

class StatusScreen(Screen):

    version = __version__
    _task_running = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._task_id = None
        self._poll_event = None
        self._status_poll = None

    def on_enter(self, *args):
        self.refresh_env()
        # 启动 2s 轮询运行状态
        if self._status_poll:
            self._status_poll.cancel()
        self._status_poll = Clock.schedule_interval(self._poll_run_status, 2)
        self._poll_run_status(0)

    def on_leave(self, *args):
        if self._status_poll:
            self._status_poll.cancel()
            self._status_poll = None

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
        bssid = wifi.get("bssid", "")
        ipv4_list = wifi.get("ipv4") or [wifi.get("ip", "--")]
        ipv6_list = wifi.get("ipv6") or []
        ipv4_str = ", ".join(ipv4_list) if ipv4_list else "--"
        ipv6_str = ", ".join(ipv6_list) if ipv6_list else "--"
        mod = info.get("module", {})
        mod_text = f"模块: {'已安装 ' + mod.get('version', '') if mod.get('installed') else '未安装'}"
        Clock.schedule_once(
            lambda dt: self._update_ui(mode, ssid, bssid, ipv4_str, ipv6_str,
                                       mod_text, info))

    def _update_ui(self, mode, ssid, bssid, ipv4, ipv6, mod_text, info):
        self.ids.env_info.text = f"模式: {mode}"
        self.ids.ssid_label.text = f"WiFi: {ssid}" + (f"  BSSID: {bssid}" if bssid else "")
        self.ids.ip_label.text = f"IPv4: {ipv4}"
        self.ids.ipv6_label.text = f"IPv6: {ipv6}"
        self.ids.mod_info.text = mod_text
        btn = self.ids.btn_webui
        if info["mode"] == "module" or (info["mode"] == "local"
                and info.get("has_root")
                and info.get("module", {}).get("installed")):
            btn.size_hint_x = 1
            btn.opacity = 1
        else:
            btn.size_hint_x = 0
            btn.opacity = 0

    # --- 运行状态轮询 ---

    def _poll_run_status(self, dt):
        app = App.get_running_app()
        if not app or not app.backend:
            return True
        threading.Thread(target=self._poll_status_bg, daemon=True).start()

    def _poll_status_bg(self):
        try:
            status = App.get_running_app().backend.get_run_status()
            Clock.schedule_once(lambda dt: self._update_run_status(status))
        except Exception:
            pass

    def _update_run_status(self, s):
        running = s.get("running", False)
        source = s.get("source")
        auto_enabled = s.get("auto_enabled", False)
        auto_connected = s.get("auto_connected", False)
        has_schedule = s.get("has_schedule", False)
        next_in = s.get("next_run_in", 0)
        waiting_first = s.get("waiting_first", False)

        self._task_running = running
        btn = self.ids.btn_login
        if running:
            src_text = "(自动)" if source == "auto" else "(手动)"
            btn.text = f"停止任务 {src_text}"
            btn.background_color = rgba('#E17055')
        else:
            btn.text = "立即认证"
            btn.background_color = rgba('#00B894')

        # 自动认证状态文本
        el = self.ids.auto_status
        if not auto_enabled:
            el.text = "自动认证未启用"
            el.color = rgba('#555568')
        elif running and source == "auto":
            el.text = "正在执行自动认证..."
            el.color = rgba('#A29BFE')
        elif running and source == "manual":
            el.text = "手动认证任务运行中"
            el.color = rgba('#A29BFE')
        elif auto_connected and has_schedule:
            el.text = f"已连接目标 WiFi，{next_in} 秒后自动执行"
            el.color = rgba('#00B894')
        elif auto_connected:
            el.text = "已连接目标 WiFi，即将执行认证..."
            el.color = rgba('#00B894')
        elif waiting_first:
            el.text = "已连接目标 WiFi，等待首次执行..."
            el.color = rgba('#FDCB6E')
        else:
            el.text = "未连接目标 WiFi，等待接入后自动触发"
            el.color = rgba('#555568')

    def do_login(self):
        app = App.get_running_app()
        if not app or not app.backend:
            return
        # 如果任务正在运行，执行停止
        if self._task_running:
            threading.Thread(target=self._stop_task_bg, daemon=True).start()
            return
        self.ids.btn_login.disabled = True
        self.ids.output.text = "正在登录...\n"
        threading.Thread(target=self._do_login_bg, daemon=True).start()

    def _stop_task_bg(self):
        ok = App.get_running_app().backend.stop_login()
        msg = "已终止认证任务" if ok else "停止失败"
        Clock.schedule_once(lambda dt: self._stop_done(ok, msg))

    def _stop_done(self, ok, msg):
        self.ids.output.text = msg + "\n"
        self.ids.auth_status.text = msg
        self.ids.auth_status.color = rgba('#00B894') if ok else rgba('#E17055')

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
        self.ids.btn_check_update.disabled = True
        # 隐藏下载按钮
        self.ids.btn_download.height = 0
        self.ids.btn_download.opacity = 0
        threading.Thread(target=self._check_update_bg, daemon=True).start()

    def _check_update_bg(self):
        app = App.get_running_app()
        if not app or not app.backend:
            return
        cfg = app.backend.load_config()
        channel = getattr(cfg, 'update_channel', 'GitHub') if cfg else 'GitHub'
        result = app.backend.check_update(channel)
        Clock.schedule_once(lambda dt: self._check_update_done(result))

    def _check_update_done(self, result):
        self.ids.btn_check_update.disabled = False
        if result.get('error'):
            self.ids.update_label.text = f"检查失败: {result['error']}"
            self.ids.update_info.text = f"渠道: {result.get('channel', '?')}"
            return
        cur = result.get('current_version', '?')
        ch = result.get('channel', 'GitHub')
        info = result.get('info', {})
        if result.get('has_update'):
            tag = info.get('tag', '')
            self.ids.update_label.text = f"新版本: {tag} (当前 {cur})"
            self.ids.update_info.text = f"渠道: {ch}"
            self.ids.btn_download.height = dp(44)
            self.ids.btn_download.opacity = 1
        else:
            tag = info.get('tag', cur)
            self.ids.update_label.text = f"已是最新 ({tag})"
            self.ids.update_info.text = f"渠道: {ch}"

    def do_update(self):
        self.ids.btn_download.disabled = True
        self.ids.btn_download.text = '下载中...'
        threading.Thread(target=self._do_update_bg, daemon=True).start()

    def _do_update_bg(self):
        ok, msg = App.get_running_app().backend.do_update()
        Clock.schedule_once(lambda dt: self._do_update_done(ok, msg))

    def _do_update_done(self, ok, msg):
        self.ids.btn_download.disabled = False
        self.ids.btn_download.text = '下载并安装更新'
        self.ids.update_info.text = msg


class AuthScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._accounts = []
        self._channels = {}
        self._task_id = None
        self._poll_event = None
        self._task_running = False
        self._status_poll = None

    def on_enter(self, *args):
        app = App.get_running_app()
        if not app or not app.backend:
            return
        threading.Thread(target=self._load_bg, daemon=True).start()
        # 启动 2s 轮询运行状态
        if self._status_poll:
            self._status_poll.cancel()
        self._status_poll = Clock.schedule_interval(self._poll_run_status, 2)
        self._poll_run_status(0)

    def on_leave(self, *args):
        if self._status_poll:
            self._status_poll.cancel()
            self._status_poll = None

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
        self.ids.suffix_spinner.set_options(ch_list)
        # 账号下拉
        self._accounts = accounts or []
        acct_list = ['选择已保存账号'] + [a.get('username', '') for a in self._accounts]
        self.ids.acct_spinner.set_options(acct_list)
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
        for i, acct in enumerate(self._accounts):
            if acct.get('username') == text:
                self.ids.username.text = acct.get('username', '')
                # 尝试获取完整密码
                threading.Thread(
                    target=self._load_account_detail_bg,
                    args=(i,), daemon=True).start()
                break

    def _load_account_detail_bg(self, index):
        detail = App.get_running_app().backend.get_account_detail(index)
        if detail:
            Clock.schedule_once(lambda dt: self._account_detail_done(detail))

    def _account_detail_done(self, detail):
        self.ids.password.text = detail.get('password', '')

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
        # 如果任务正在运行，执行停止
        if self._task_running:
            threading.Thread(target=self._stop_task_bg, daemon=True).start()
            return
        self.ids.btn_login.disabled = True
        self.ids.auth_output.text = '正在登录...\n'
        threading.Thread(target=self._do_login_bg, daemon=True).start()

    def _stop_task_bg(self):
        ok = App.get_running_app().backend.stop_login()
        msg = "已终止认证任务" if ok else "停止失败"
        Clock.schedule_once(lambda dt: self._stop_done(ok, msg))

    def _stop_done(self, ok, msg):
        self.ids.auth_output.text = msg + "\n"
        self.ids.auth_status.text = msg
        self.ids.auth_status.color = rgba('#00B894') if ok else rgba('#E17055')
        self._task_running = False
        self.ids.btn_login.text = '立即认证'
        self.ids.btn_login.background_color = rgba('#00B894')

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
        self._task_running = False
        self.ids.btn_login.text = '立即认证'
        self.ids.btn_login.background_color = rgba('#00B894')
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

    # --- 账号还原 ---

    def restore_account(self):
        """将选中的已保存账号还原到认证配置表单"""
        text = self.ids.acct_spinner.text
        if text == '选择已保存账号' or not text:
            self.ids.acct_status.text = '请先选择要还原的账号'
            self.ids.acct_status.color = rgba('#E17055')
            return
        for i, acct in enumerate(self._accounts):
            if acct.get('username') == text:
                self.ids.username.text = acct.get('username', '')
                threading.Thread(
                    target=self._restore_acct_bg, args=(i,),
                    daemon=True).start()
                return
        self.ids.acct_status.text = '账号未找到'
        self.ids.acct_status.color = rgba('#E17055')

    def _restore_acct_bg(self, index):
        detail = App.get_running_app().backend.get_account_detail(index)
        if detail:
            Clock.schedule_once(lambda dt: self._restore_acct_done(detail))

    def _restore_acct_done(self, detail):
        self.ids.password.text = detail.get('password', '')
        self.ids.acct_status.text = f"已还原: {detail.get('username', '')}"
        self.ids.acct_status.color = rgba('#00B894')

    # --- 运行状态轮询 ---

    def _poll_run_status(self, dt):
        app = App.get_running_app()
        if not app or not app.backend:
            return True
        threading.Thread(target=self._poll_status_bg, daemon=True).start()

    def _poll_status_bg(self):
        try:
            status = App.get_running_app().backend.get_run_status()
            Clock.schedule_once(lambda dt: self._update_run_status(status))
        except Exception:
            pass

    def _update_run_status(self, s):
        running = s.get("running", False)
        source = s.get("source")
        self._task_running = running
        btn = self.ids.btn_login
        if running:
            src_text = "(自动)" if source == "auto" else "(手动)"
            btn.text = f"停止任务 {src_text}"
            btn.background_color = rgba('#E17055')
        else:
            btn.text = "立即认证"
            btn.background_color = rgba('#00B894')


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
            self.ids.auto_interval.text = str(getattr(cfg, 'auto_interval', 5))
            self.ids.auto_delay.text = str(getattr(cfg, 'auto_delay', 5))

    def save(self):
        app = App.get_running_app()
        if not app or not app.backend:
            return
        cfg = app.backend.load_config() or DrComConfig()
        cfg.auto_run = self.ids.auto_run.state == 'down'
        cfg.target_essid = self.ids.target_essid.text.strip()
        # 间隔/延迟
        try:
            interval = int(self.ids.auto_interval.text or 5)
            if interval < 1:
                raise ValueError
        except ValueError:
            self.ids.auto_status.text = '间隔需为不小于 1 的整数'
            self.ids.auto_status.color = rgba('#E17055')
            return
        try:
            delay = int(self.ids.auto_delay.text or 5)
            if delay < 0:
                raise ValueError
        except ValueError:
            self.ids.auto_status.text = '延迟需为非负整数'
            self.ids.auto_status.color = rgba('#E17055')
            return
        cfg.auto_interval = interval
        cfg.auto_delay = delay
        threading.Thread(target=self._save_bg, args=(cfg,), daemon=True).start()
        self.ids.auto_status.text = '保存中...'
        self.ids.auto_status.color = rgba('#A29BFE')

    def fill_essid(self):
        """获取当前 WiFi SSID 填充到目标 ESSID"""
        app = App.get_running_app()
        if not app or not app.backend:
            return
        threading.Thread(target=self._fill_essid_bg, daemon=True).start()

    def _fill_essid_bg(self):
        wifi = App.get_running_app().backend.get_wifi_info()
        ssid = wifi.get('ssid', '')
        Clock.schedule_once(lambda dt: self._fill_essid_done(ssid))

    def _fill_essid_done(self, ssid):
        if ssid:
            self.ids.target_essid.text = ssid
            self.ids.auto_status.text = f'已填充: {ssid}'
            self.ids.auto_status.color = rgba('#A29BFE')
        else:
            self.ids.auto_status.text = '未连接 WiFi 或无法获取名称'
            self.ids.auto_status.color = rgba('#E17055')

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
            # 新增字段
            self.ids.port_input.text = str(getattr(cfg, 'port', 38080))
            self.ids.log_file_input.text = getattr(cfg, 'log_file', '') or ''
            self.ids.download_dir_input.text = getattr(cfg, 'download_dir', '') or ''
            ch = getattr(cfg, 'update_channel', 'GitHub') or 'GitHub'
            self.ids.update_channel_spinner.text = ch
            self.ids.auto_open_webui_switch.state = 'down' if getattr(cfg, 'auto_open_webui', False) else 'normal'
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
                _btn_base = (0.06, 0.06, 0.08, 1)
                _btn_dark = (0.04, 0.04, 0.06, 1)
                btn = Button(
                    text=f"  {acct.get('username', '')}",
                    size_hint_x=1, background_normal='', background_down='',
                    background_color=_btn_base,
                    color=(0.88, 0.88, 0.93, 1),
                    font_name='Roboto', font_size='14sp',
                    halign='left', valign='middle')
                btn.bind(on_press=lambda inst, c=_btn_dark: (setattr(inst, 'background_color', c), Clock.schedule_once(lambda dt, b=inst, rc=_btn_base: setattr(b, 'background_color', rc), 0.15)),
                         on_release=lambda inst, c=_btn_base: setattr(inst, 'background_color', c))
                btn.bind(on_press=lambda inst, idx=i: self._select_acct(idx))
                row.add_widget(btn)
                _del_base = (0.165, 0.165, 0.227, 1)
                _del_dark = (0.12, 0.12, 0.17, 1)
                del_btn = Button(
                    text='删除', size_hint_x=None, width=dp(56),
                    background_normal='', background_down='',
                    background_color=_del_base,
                    color=(0.88, 0.44, 0.33, 1),
                    font_name='Roboto', font_size='12sp')
                del_btn.bind(on_press=lambda inst, c=_del_dark: (setattr(inst, 'background_color', c), Clock.schedule_once(lambda dt, b=inst, rc=_del_base: setattr(b, 'background_color', rc), 0.15)),
                             on_release=lambda inst, c=_del_base: setattr(inst, 'background_color', c))
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
                _btn_base = (0.165, 0.165, 0.227, 1)
                _btn_dark = (0.12, 0.12, 0.17, 1)
                edit_btn = Button(
                    text='编辑', size_hint_x=None, width=dp(48),
                    background_normal='', background_down='',
                    background_color=_btn_base,
                    color=(0.42, 0.36, 0.91, 1),
                    font_name='Roboto', font_size='12sp')
                edit_btn.bind(on_press=lambda inst, c=_btn_dark: (setattr(inst, 'background_color', c), Clock.schedule_once(lambda dt, b=inst, rc=_btn_base: setattr(b, 'background_color', rc), 0.15)),
                              on_release=lambda inst, c=_btn_base: setattr(inst, 'background_color', c))
                edit_btn.bind(on_press=lambda inst, s=suffix, l=label: self._select_channel(s, l))
                row.add_widget(edit_btn)
                del_btn = Button(
                    text='删除', size_hint_x=None, width=dp(56),
                    background_normal='', background_down='',
                    background_color=_btn_base,
                    color=(0.88, 0.44, 0.33, 1),
                    font_name='Roboto', font_size='12sp')
                del_btn.bind(on_press=lambda inst, c=_btn_dark: (setattr(inst, 'background_color', c), Clock.schedule_once(lambda dt, b=inst, rc=_btn_base: setattr(b, 'background_color', rc), 0.15)),
                             on_release=lambda inst, c=_btn_base: setattr(inst, 'background_color', c))
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

    # --- 服务设置 ---

    def save_network(self):
        app = App.get_running_app()
        if not app or not app.backend:
            return
        cfg = app.backend.load_config() or DrComConfig()
        cfg.auth_server = self.ids.auth_server.text.strip()
        cfg.redirect_server = self.ids.redirect_server.text.strip()
        cfg.debug = self.ids.debug_switch.state == 'down'
        # 新增字段
        try:
            port = int(self.ids.port_input.text or 38080)
            if not (1 <= port <= 65535):
                raise ValueError
        except ValueError:
            self.ids.net_status.text = '端口范围 1-65535'
            self.ids.net_status.color = rgba('#E17055')
            return
        cfg.port = port
        cfg.log_file = self.ids.log_file_input.text.strip()
        cfg.download_dir = self.ids.download_dir_input.text.strip()
        cfg.update_channel = self.ids.update_channel_spinner.text
        cfg.auto_open_webui = self.ids.auto_open_webui_switch.state == 'down'
        threading.Thread(target=self._save_net_bg, args=(cfg,), daemon=True).start()
        self.ids.net_status.text = '保存中...'
        self.ids.net_status.color = rgba('#A29BFE')

    def _save_net_bg(self, cfg):
        ok = App.get_running_app().backend.save_config(cfg)
        Clock.schedule_once(lambda dt: self._save_net_done(ok))

    def _save_net_done(self, ok):
        if ok:
            self.ids.net_status.text = '服务设置已保存'
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
