#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""drcom_core 单元测试（本地 venv 可跑：python3 -m unittest tests/test_drcom_core.py）"""

import base64
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

# 让测试能找到 drcom_core
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import drcom_core
from drcom_core import (
    DrComConfig, LoginState,
    build_login_url, build_logout_url,
    parse_login_response, perform_login, perform_logout,
    _parse_302, _parse_xml_comment,
    probe_ipv6,
)


class TestDrComConfig(unittest.TestCase):
    def test_defaults(self):
        c = DrComConfig(username="u", password="p")
        self.assertEqual(c.suffix, "@cmcc")
        self.assertEqual(c.auth_server, "10.0.1.5")
        self.assertEqual(c.redirect_server, "1.2.3.4")
        self.assertEqual(c.timeout, 5)
        self.assertFalse(c.debug)


class TestLoginState(unittest.TestCase):
    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "state.json")
            state = LoginState(host="h", username="u", mac="m", ip="i")
            self.assertTrue(state.save(path))
            loaded = LoginState.load(path)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.host, "h")
            self.assertEqual(loaded.username, "u")
            self.assertEqual(loaded.mac, "m")
            self.assertEqual(loaded.ip, "i")
            # 权限检查（仅 Unix）
            if os.name != "nt":
                mode = os.stat(path).st_mode & 0o777
                self.assertEqual(mode, 0o600)

    def test_load_missing(self):
        self.assertIsNone(LoginState.load("/nonexistent/path.json"))

    def test_load_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not json")
            path = f.name
        try:
            self.assertIsNone(LoginState.load(path))
        finally:
            os.unlink(path)


class TestBuildLoginUrl(unittest.TestCase):
    def test_url_structure(self):
        cfg = DrComConfig(username="2400470220", password="secret",
                          suffix="@cmcc", ipv6="")
        url = build_login_url(cfg, host="10.0.1.5",
                              wlan_user_ip="169991176",
                              wlan_ac_name="acname",
                              wlan_ac_ip="10.0.0.1",
                              wlan_user_mac="8e0d2c953773")
        parsed = urlparse(url)
        self.assertEqual(parsed.scheme, "http")
        self.assertEqual(parsed.hostname, "10.0.1.5")
        self.assertEqual(parsed.port, 801)
        self.assertEqual(parsed.path, "/eportal/portal/login")
        params = parse_qs(parsed.query)
        # user_account 必须是 ,0,username@suffix 格式
        self.assertEqual(params["user_account"][0], ",0,2400470220@cmcc")
        # 密码 base64
        self.assertEqual(params["user_password"][0],
                         base64.b64encode(b"secret").decode())
        # 其他固定参数
        self.assertEqual(params["wlan_user_ip"][0], "169991176")
        self.assertEqual(params["wlan_user_mac"][0], "8e0d2c953773")
        self.assertEqual(params["wlan_ac_ip"][0], "10.0.0.1")
        self.assertEqual(params["wlan_ac_name"][0], "acname")
        self.assertEqual(params["callback"][0], "dr1004")
        self.assertEqual(params["login_method"][0], "1")
        self.assertEqual(params["lang"][0], "en")


class TestBuildLogoutUrl(unittest.TestCase):
    """登出 URL golden 测试：与 v2.7.3 修复后的 URL 逐参比对。"""
    def test_logout_url_matches_golden(self):
        url = build_logout_url(host="10.0.1.5", username="2400470220",
                               mac="8E0D2C953773", ip="169991176")
        parsed = urlparse(url)
        self.assertEqual(parsed.hostname, "10.0.1.5")
        self.assertEqual(parsed.port, 801)
        self.assertEqual(parsed.path, "/eportal/portal/mac/unbind")
        params = parse_qs(parsed.query)
        # 关键：user_account 必须是纯用户名（无 ,0, 无 @cmcc）
        self.assertEqual(params["user_account"][0], "2400470220")
        self.assertEqual(params["wlan_user_mac"][0], "8E0D2C953773")
        self.assertEqual(params["wlan_user_ip"][0], "169991176")
        self.assertEqual(params["callback"][0], "dr1002")
        self.assertEqual(params["jsVersion"][0], "4.2")
        self.assertEqual(params["lang"][0], "en")


class TestParseGatewayResponse(unittest.TestCase):
    def test_parse_302_location(self):
        loc = ("http://10.0.1.5:801/eportal/portal/login?"
               "wlanuserip=169991176&wlanacname=AC-1&wlanacip=10.0.0.1"
               "&wlanusermac=8E:0D:2C:95:37:73")
        host, ip, ac_name, ac_ip, mac = _parse_302(loc)
        self.assertEqual(host, "10.0.1.5")
        self.assertEqual(ip, "169991176")
        self.assertEqual(ac_name, "AC-1")
        self.assertEqual(ac_ip, "10.0.0.1")
        # mac 去除分隔符并小写
        self.assertEqual(mac, "8e0d2c953773")

    def test_parse_302_missing_param(self):
        loc = "http://10.0.1.5/?wlanuserip=1.2.3.4"
        result = _parse_302(loc)
        self.assertEqual(result, (None,) * 5)

    def test_parse_xml_comment(self):
        xml = ('''<!--
        <WISPAccessGatewayParam>
          <Proxy>
            <NextURL>http://10.0.1.5/?wlanuserip=169991176&amp;wlanacname=AC-1&amp;wlanacip=10.0.0.1&amp;wlanusermac=8E0D2C953773</NextURL>
          </Proxy>
        </WISPAccessGatewayParam>
        -->''')
        host, ip, ac_name, ac_ip, mac = _parse_xml_comment(xml)
        self.assertEqual(host, "10.0.1.5")
        self.assertEqual(ip, "169991176")
        self.assertEqual(ac_name, "AC-1")
        self.assertEqual(mac, "8e0d2c953773")

    def test_parse_xml_no_match(self):
        self.assertEqual(_parse_xml_comment("not xml"), (None,) * 5)


class TestParseLoginResponse(unittest.TestCase):
    def test_success_v1(self):
        ok, msg = parse_login_response('{"result":1,"msg":"authentication succeeded"}')
        self.assertTrue(ok)

    def test_success_v2(self):
        ok, _ = parse_login_response('dr1004({"result":1,"msg":"OK"})')
        self.assertTrue(ok)

    def test_failure_with_msg(self):
        ok, msg = parse_login_response('dr1004({"result":0,"msg":"密码错误"})')
        self.assertFalse(ok)
        self.assertIn("密码错误", msg)

    def test_empty(self):
        ok, _ = parse_login_response("")
        self.assertFalse(ok)


class TestPerformLogout(unittest.TestCase):
    @patch("drcom_core.requests.get")
    def test_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = 'dr1002({"result":1})'
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp
        ok, text = perform_logout("10.0.1.5", "u", "m", "i", timeout=3)
        self.assertTrue(ok)
        self.assertIn("result", text)


if __name__ == "__main__":
    unittest.main()
