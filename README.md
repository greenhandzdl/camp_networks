# Dr.COM 校园网认证脚本 (有线 & 无线)

本项目提供针对 Dr.COM 认证系统的自动登录脚本，支持**有线网络**（直接 `/drcom/login` 接口）和**无线网络**（通过 `1.2.3.4` 网关获取参数两种方式）。脚本使用 Python 3 编写，可运行于 Windows / Linux / macOS。

---

## 📁 项目结构

```
camp_networks/
├── LICENSE
├── README.md
├── python_vers/
│   ├── requirements.txt
│   ├── drcom_core.py          # 平台无关认证核心库（模块 + APK 共用）
│   ├── wired_login.py         # 有线版认证脚本
│   ├── wlan_login.py          # 无线认证 CLI（薄封装 drcom_core）
│   ├── wlan_logout.py         # 登出 CLI（薄封装 drcom_core）
│   ├── webui.py               # WebUI HTTP 服务主程序
│   ├── webui_utils/           # WebUI 工具模块
│   ├── tests/                 # 单元测试
│   ├── .env                   # 本地环境变量（不提交）
│   └── .env.example           # 环境变量模板
└── android_app/               # Kivy APK 工程
    ├── buildozer.spec
    ├── build_apk.sh
    └── app/
        ├── main.py            # Kivy App 入口
        ├── backend.py         # LocalBackend / ModuleBackend 抽象
        └── native_net.py      # pyjnius WifiManager
```

---

## 🚀 快速开始

### 1. 安装依赖

```bash
cd python_vers
pip install -r requirements.txt
```

`requirements.txt` 内容示例：
```
requests>=2.25.0
python-dotenv>=0.19.0
```

### 2. 配置账号信息

复制 `.env.example` 为 `.env`，并填写实际信息：

```bash
cp .env.example .env
```

编辑 `.env`：

```ini
# 通用配置
USERNAME=your_username          # 你的学号/账号
PASSWORD=your_password      # 你的密码
ACCOUNT_SUFFIX=@cmcc         # 运营商后缀（@cmcc / @telecom / @unicom）
DEBUG=false                  # 是否输出调试信息（true/false）

# 有线版专用
AUTH_SERVER=10.0.1.5         # 认证服务器 IP（一般固定）

# 无线版专用
# 无线版会自动从网关获取参数，无需额外配置
```

### 3. 运行脚本

- **有线网络环境**（已获取 IP，无需无线网关参数）：
  ```bash
  python wired_login.py
  ```

- **无线网络环境**（需通过 `1.2.3.4` 网关获取认证参数）：
  ```bash
  python wlan_login.py
  ```

---

## 📖 脚本说明

### `wired_login.py` – 有线版

- **适用场景**：通过有线网卡连接校园网，已获得有效 IPv4/IPv6 地址，直接向认证服务器发送登录请求。
- **认证接口**：`http://{AUTH_SERVER}/drcom/login`
- **请求参数**：`callback`, `DDDDD`, `upass`, `v4ip`, `v6ip`, `0MKKey`, `R1`~`R6`, `para`, `terminal_type`, `lang`, `jsVersion`, `v`
- **特点**：
  - 自动获取本机出口 IPv4 和全局 IPv6 地址。
  - 密码以明文传输（协议本身如此）。
  - 响应为 JSONP 格式（`dr1004({...})`），脚本自动解析。

### `wlan_login.py` – 无线版

- **适用场景**：通过无线网卡连接校园 Wi-Fi，需通过网关 `1.2.3.4` 重定向获取 `wlan_*` 参数后再认证。
- **认证流程**：
  1. 检测外网连通性，若已通则退出。
  2. 访问 `http://1.2.3.4` 获取重定向参数（`wlanuserip`, `wlanacname`, `wlanacip`, `wlanusermac`）。
  3. 构造请求并发送至 `http://{host}:801/eportal/portal/login`。
- **参数特点**：
  - 用户名格式：`,0,账号@后缀`
  - 密码使用 Base64 编码。
  - 包含 `user_account`, `user_password`, `wlan_user_ip`, `wlan_user_ipv6`, `wlan_ac_name`, `wlan_ac_ip`, `wlan_user_mac` 等。

---

## ⚙️ 环境变量详解

| 变量名 | 说明 | 默认值 | 适用版本 |
|--------|------|--------|----------|
| `USERNAME` | 账号（不含后缀） | 无 | 全部 |
| `PASSWORD` | 密码 | 无 | 全部 |
| `ACCOUNT_SUFFIX` | 运营商后缀，如 `@cmcc` | `@cmcc` | 全部 |
| `DEBUG` | 是否输出调试信息 | `false` | 全部 |
| `AUTH_SERVER` | 有线认证服务器 IP | `10.0.1.5` | 有线版 |
| `IPV6_ADDRESS` | 手动指定 IPv6（可选） | 空（自动获取） | 无线版 |

---

## 🔄 退出码说明

脚本返回以下状态码，便于自动化流程判断：

| 退出码 | 含义 |
|--------|------|
| 0 | 认证成功（或已在线） |
| 1 | 外网和网关均不可达（网络物理故障） |
| 2 | （无线版）获取网关参数失败（解析错误） |
| 3 | 登录请求发送失败（服务器无响应） |
| 4 | 认证失败（账号/密码错误或参数不匹配） |
| 5 | 登录请求已发送，但外网仍未连通（可能需人工检查） |

---

## 🛠 调试与排错

- **开启调试模式**：在 `.env` 中设置 `DEBUG=true`，脚本会打印详细的请求 URL、响应内容等。
- **手动测试**：可先用浏览器或 `curl` 访问认证地址，观察是否正常。
- **常见问题**：
  - *IP 获取失败*：确保网络已连接，或手动在脚本中指定 IP（修改 `get_local_ipv4/6` 函数）。
  - *认证响应显示 `result:0`*：检查账号密码及后缀是否正确。
  - *有线版超时*：确认 `AUTH_SERVER` 是否可达（`ping 10.0.1.5`）。

---

## 📜 许可证

本项目采用 MIT 许可证，详见 [LICENSE](LICENSE) 文件。

---

## 🤝 贡献

欢迎提交 Issue 或 Pull Request。若有其他认证接口版本，也可在此基础上扩展。

---

> **注意**：本脚本仅供学习与研究使用，请勿用于任何违规用途。使用前请确保已获得校园网管理方的授权。

---

## Kivy APK

`android_app/` 提供 Kivy 跨平台 APK 工程，复用 `drcom_core.py` 认证核心：

- **无 root**：本地模式，APK 内直接执行认证
- **root + 模块已装**：模块模式，通过 WebUI HTTP API 操作

构建 APK：
```bash
cd android_app
pip install buildozer
bash build_apk.sh
```