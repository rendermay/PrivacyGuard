#!/bin/bash
#
# SecureRedact macOS 应用打包脚本
# 版本: from version.txt
# 说明: 自动化打包 macOS .app 和 DMG 安装包
#

set -euo pipefail

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目信息
APP_NAME="SecureRedact"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# 从 scripts -> macos -> packaging -> project_root
PROJECT_ROOT="$(dirname "$(dirname "$(dirname "$SCRIPT_DIR")")")"

# 从 version.txt 读取版本号
VERSION=$(cat "${PROJECT_ROOT}/version.txt" | tr -d '[:space:]')
if [ -z "$VERSION" ]; then
    echo "错误: 无法读取 version.txt"
    exit 1
fi

BUNDLE_ID="com.secureredact.app"
MACOS_DIR="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="${PROJECT_ROOT}/build"
DIST_DIR="${PROJECT_ROOT}/dist"
RELEASE_DIR="${PROJECT_ROOT}/releases/macos"
PYINSTALLER_CONFIG_DIR="${BUILD_DIR}/.pyinstaller-cache"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  SecureRedact macOS 打包脚本${NC}"
echo -e "${BLUE}  版本: ${VERSION}${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# ========================================
# 函数定义
# ========================================

print_step() {
    echo -e "${GREEN}[步骤]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[信息]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[警告]${NC} $1"
}

print_error() {
    echo -e "${RED}[错误]${NC} $1"
}

# ========================================
# 步骤 1: 环境检查
# ========================================
print_step "检查打包环境"

# 检查 Python 环境
if ! command -v python3 &> /dev/null; then
    print_error "未找到 Python3"
    exit 1
fi

# 激活虚拟环境（优先 venvmac，兼容 venv）
if [ -f "${PROJECT_ROOT}/venvmac/bin/activate" ]; then
    print_info "激活虚拟环境: venvmac"
    source "${PROJECT_ROOT}/venvmac/bin/activate"
elif [ -f "${PROJECT_ROOT}/venv/bin/activate" ]; then
    print_info "激活虚拟环境: venv"
    source "${PROJECT_ROOT}/venv/bin/activate"
else
    print_warn "未找到虚拟环境，使用系统 Python"
fi

# 安装/校验锁定版构建依赖 (P0-5: pyinstaller + pyinstaller-hooks-contrib 必须锁版本)
# jieba 的 5MB 词典(jieba/dict.txt)只能靠 hooks-contrib 的 hook-jieba.py 进包，
# 缺失则打包版中文姓名识别静默失效且无任何报错。
print_info "安装锁定版构建依赖 (packaging/requirements-build.txt)"
python3 -m pip install -r "${PROJECT_ROOT}/packaging/requirements-build.txt"

# 检查图标文件
# 注意: 必须与 spec 中 BUNDLE(icon=...) 传入的路径保持一致。
# packaging/macos/config/SecureRedact.spec 用的是项目根 assets/logo/macos/AppIcon.icns
# （旧的 packaging/macos/assets/PrivacyGuard.icns 是重命名前的遗留副本，spec 未引用）。
# 之前这里检查的是 assets/SecureRedact.icns —— 该文件从不存在，脚本会在此行 100% exit 1。
APP_ICON="${PROJECT_ROOT}/assets/logo/macos/AppIcon.icns"
APP_ICON_NAME="$(basename "${APP_ICON}")"
if [ ! -f "${APP_ICON}" ]; then
    print_error "未找到图标文件: ${APP_ICON}"
    exit 1
fi
print_info "应用图标: ${APP_ICON}"

# 检查 spec 文件
if [ ! -f "${MACOS_DIR}/config/SecureRedact.spec" ]; then
    print_error "未找到打包配置文件: SecureRedact.spec"
    exit 1
fi

# 校验 spec 的 datas 路径（不实际打包）
# version.txt / config.json 必须打进应用目录，否则运行时版本号与配置会退化。
if ! python3 "${PROJECT_ROOT}/packaging/verify_spec_datas.py"; then
    print_error "Spec 校验失败: 请检查 packaging/macos/config/SecureRedact.spec 的 datas 条目"
    exit 1
fi

# ========================================
# 步骤 2: 清理旧构建
# ========================================
print_step "清理旧构建文件"

rm -rf "${BUILD_DIR}"
rm -rf "${DIST_DIR}"
rm -rf "${PROJECT_ROOT}/__pycache__"
mkdir -p "${BUILD_DIR}"
mkdir -p "${PYINSTALLER_CONFIG_DIR}"

print_info "清理完成"

# ========================================
# 步骤 3: 执行 PyInstaller 打包
# ========================================
print_step "执行 PyInstaller 打包（这可能需要几分钟）"

cd "${PROJECT_ROOT}"

export PYINSTALLER_CONFIG_DIR
print_info "使用本地 PyInstaller 缓存: ${PYINSTALLER_CONFIG_DIR}"

python3 -m PyInstaller --clean \
    --noconfirm \
    "${MACOS_DIR}/config/SecureRedact.spec"

print_info "PyInstaller 打包完成"

# ========================================
# 步骤 4: 验证 .app 结构
# ========================================
print_step "验证 .app 结构"

APP_PATH="${DIST_DIR}/${APP_NAME}.app"

if [ ! -d "${APP_PATH}" ]; then
    print_error ".app 文件生成失败"
    exit 1
fi

# 检查必需的文件
REQUIRED_FILES=(
    "Contents/MacOS/${APP_NAME}"
    "Contents/Info.plist"
    # PyInstaller 的 BUNDLE 会把 icns 原样拷贝到 Contents/Resources/<icns 文件名>
    # (osx.py: shutil.copyfile(self.icon, .../Contents/Resources/basename(self.icon)))
    # 因此这里必须是 AppIcon.icns，而不是 ${APP_NAME}.icns。
    "Contents/Resources/${APP_ICON_NAME}"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -e "${APP_PATH}/${file}" ]; then
        print_error "缺少必需文件: ${file}"
        exit 1
    fi
done

# P0-1: version.txt 必须随包分发（缺失会落 fallback "1.1.12"，与 Info.plist 版本不一致）
if [ -f "${APP_PATH}/Contents/Resources/version.txt" ] || [ -f "${APP_PATH}/Contents/Frameworks/version.txt" ]; then
    print_info "version.txt 存在"
else
    print_error "version.txt 未打进 .app"
    print_error "请检查 packaging/macos/config/SecureRedact.spec 的 datas 是否包含 version.txt"
    exit 1
fi

# P0-2: config.json 必须随包分发（应用目录）
if [ -f "${APP_PATH}/Contents/Resources/config.json" ] || [ -f "${APP_PATH}/Contents/Frameworks/config.json" ]; then
    print_info "config.json 存在"
else
    print_error "config.json 未打进 .app"
    print_error "请检查 packaging/macos/config/SecureRedact.spec 的 datas 是否包含 config.json"
    exit 1
fi

print_info ".app 结构验证通过"

# 显示应用大小
APP_SIZE=$(du -sh "${APP_PATH}" | cut -f1)
print_info "应用大小: ${APP_SIZE}"

# ========================================
# 步骤 5: 创建 DMG 安装包
# ========================================
print_step "创建 DMG 安装包"

# 创建 releases 目录
mkdir -p "${RELEASE_DIR}"

DMG_NAME="${APP_NAME}-${VERSION}-macOS.dmg"
DMG_PATH="${RELEASE_DIR}/${DMG_NAME}"

# 删除旧的 DMG
if [ -f "${DMG_PATH}" ]; then
    rm "${DMG_PATH}"
fi

# 创建临时 DMG 目录
DMG_TEMP_DIR="${PROJECT_ROOT}/dmg_temp"
rm -rf "${DMG_TEMP_DIR}"
mkdir -p "${DMG_TEMP_DIR}"

# 复制 .app 到临时目录
cp -R "${APP_PATH}" "${DMG_TEMP_DIR}/"

# 创建 Applications 链接
ln -s /Applications "${DMG_TEMP_DIR}/Applications"

# 创建 DMG
print_info "正在创建 DMG 镜像..."

# 使用 hdiutil 创建 DMG
if ! hdiutil create -volname "${APP_NAME}" \
    -srcfolder "${DMG_TEMP_DIR}" \
    -ov \
    -format UDZO \
    "${DMG_PATH}" 2>&1 | while read line; do echo "  $line"; done; then
    print_error "DMG 创建失败"
    rm -rf "${DMG_TEMP_DIR}"
    exit 1
fi

# 清理临时目录
rm -rf "${DMG_TEMP_DIR}"

if [ ! -f "${DMG_PATH}" ]; then
    print_error "DMG 创建失败"
    exit 1
fi

DMG_SIZE=$(du -sh "${DMG_PATH}" | cut -f1)
print_info "DMG 创建完成: ${DMG_PATH} (${DMG_SIZE})"

# ========================================
# 步骤 6: 生成校验和
# ========================================
print_step "生成文件校验和"

cd "${RELEASE_DIR}"

# 生成 SHA256
shasum -a 256 "${DMG_NAME}" > "${DMG_NAME}.sha256"
print_info "SHA256 校验和已生成"

# ========================================
# 步骤 7: 打包完成
# ========================================
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  打包完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}应用位置:${NC}"
echo -e "   .app:  ${APP_PATH}"
echo -e "   DMG:   ${DMG_PATH}"
echo ""
echo -e "${BLUE}文件大小:${NC}"
echo -e "   .app:  ${APP_SIZE}"
echo -e "   DMG:   ${DMG_SIZE}"
echo ""
echo -e "${BLUE}校验和:${NC}"
cat "${DMG_NAME}.sha256"
echo ""
echo -e "${BLUE}下一步操作:${NC}"
echo -e "   1. 双击 ${DMG_NAME} 安装"
echo -e "   2. 将 ${APP_NAME}.app 拖入 Applications 文件夹"
echo -e "   3. 首次运行需右键点击应用选择'打开'"
echo ""
echo -e "${YELLOW}注意:${NC}"
echo -e "   • 应用未签名，首次运行需要手动允许"
echo -e "   • 右键点击应用 > 打开 > 仍要打开"
echo ""

# 返回原目录
cd "${PROJECT_ROOT}"
