#!/usr/bin/env bash
# ============================================================
# build_apk.sh — 构建 Kivy APK（本地 / CI 通用）
#
# 流程：
#   1. 拷贝 drcom_core.py（保持单一事实源）
#   2. 注入版本号（CI 通过环境变量 VERSION_NAME / VERSION_CODE 传入）
#   3. 调用 buildozer 构建
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$SCRIPT_DIR/app"
CORE_SRC="$SCRIPT_DIR/../python_vers/drcom_core.py"
SPEC_FILE="$SCRIPT_DIR/buildozer.spec"

# ---------- 颜色 ----------
RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
info() { echo -e "${CYAN}[INFO]${NC} $*"; }
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ---------- 检查环境 ----------
command -v buildozer >/dev/null 2>&1 || { err "buildozer 未安装：pip install buildozer"; exit 1; }

# ---------- 1. 拷贝 drcom_core.py（单一事实源在 python_vers/ 下）----------
if [ ! -f "$CORE_SRC" ]; then
    err "找不到 $CORE_SRC"
    exit 1
fi
info "拷贝 drcom_core.py 到 app/"
cp "$CORE_SRC" "$APP_DIR/drcom_core.py"
ok "已同步 drcom_core.py"

# ---------- 2. 注入版本号（CI 通过环境变量传入）----------
VERSION_NAME="${VERSION_NAME:-3.0.0}"
VERSION_CODE="${VERSION_CODE:-29}"

# 写入 buildozer.spec（仅改 version 字段，不动其他）
if grep -q "^version = " "$SPEC_FILE"; then
    sed -i.bak "s|^version = .*|version = $VERSION_NAME|" "$SPEC_FILE"
    rm -f "${SPEC_FILE}.bak"
fi

# 写入 app/version.py 供运行时读取（避免 spec 读取复杂）
cat > "$APP_DIR/version.py" <<EOF
# 由 build_apk.sh 自动生成，不要手动修改
__version__ = "$VERSION_NAME"
__version_code__ = $VERSION_CODE
EOF
ok "注入版本: $VERSION_NAME (code=$VERSION_CODE)"

# ---------- 3. 构建 ----------
cd "$SCRIPT_DIR"
info "执行 buildozer android debug"
buildozer android debug

# 产物路径
APK_PATH="$SCRIPT_DIR/bin/${PACKAGE_NAME:-drcomwlan}-${VERSION_NAME}-debug.apk"
# buildozer 默认输出路径
APK_DEFAULT="$SCRIPT_DIR/bin/drcomwlan-${VERSION_NAME}-debug.apk"
if [ -f "$APK_DEFAULT" ]; then
    APK_PATH="$APK_DEFAULT"
fi

ok "构建完成: $APK_PATH"
echo ""
echo "APK 路径: $APK_PATH"
echo "文件大小: $(du -h "$APK_PATH" 2>/dev/null | cut -f1 || echo "unknown")"
