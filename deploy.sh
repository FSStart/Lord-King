#!/bin/bash
# Nexus AI 一键部署脚本 (修复版)

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# ===== 配置 =====
SERVER="root@110.42.217.122"
PROJECT_PATH="/root/Lord-King"

MSG="${1:-update}"

echo -e "${CYAN}═══════════════════════════════════════${NC}"
echo -e "${CYAN}   🚀 Nexus AI 一键部署${NC}"
echo -e "${CYAN}═══════════════════════════════════════${NC}"

# === 1. 本地 git add + commit ===
echo -e "\n${YELLOW}[1/4]${NC} 检查本地修改..."
git add .

if git diff --cached --quiet; then
    echo -e "${YELLOW}  ⓘ 没有需要提交的修改${NC}"
    NEED_PUSH=false
else
    git diff --cached --stat
    git commit -m "$MSG" || { echo -e "${RED}❌ commit 失败${NC}"; exit 1; }
    NEED_PUSH=true
fi

# === 2. push ===
if [ "$NEED_PUSH" = true ]; then
    echo -e "\n${YELLOW}[2/4]${NC} 推送到 GitHub..."
    git push || { echo -e "${RED}❌ push 失败${NC}"; exit 1; }
    echo -e "${GREEN}  ✓ 已推送${NC}"
else
    echo -e "\n${YELLOW}[2/4]${NC} 跳过 push(无变化)"
fi

# === 3. 服务器拉取 ===
echo -e "\n${YELLOW}[3/4]${NC} 服务器拉取代码..."
PULL_OUTPUT=$(ssh "$SERVER" "cd $PROJECT_PATH && git pull" 2>&1)
echo "$PULL_OUTPUT"

if echo "$PULL_OUTPUT" | grep -q "Already up to date"; then
    echo -e "${YELLOW}  ⓘ 服务器代码已是最新${NC}"
    HAS_CHANGES=false
else
    HAS_CHANGES=true
fi

# === 4. 智能重启(把脚本写成单引号字符串,避免转义问题) ===
echo -e "\n${YELLOW}[4/4]${NC} 智能重启服务..."

if [ "$HAS_CHANGES" = false ]; then
    echo -e "${YELLOW}  ⓘ 无变化,不需要重启${NC}"
else
    # 远程执行的脚本用单引号包裹,避免本地shell处理
    ssh "$SERVER" 'bash -s' <<'REMOTE_SCRIPT'
cd /root/Lord-King

CHANGED=$(git diff --name-only HEAD@{1} HEAD 2>/dev/null)
echo "变更文件:"
echo "$CHANGED" | sed 's/^/  - /'

if echo "$CHANGED" | grep -qE 'requirements\.txt|Dockerfile'; then
    echo "🔨 检测到依赖变化,重建后端镜像(3-5分钟)..."
    docker compose build --no-cache backend && docker compose up -d backend
elif echo "$CHANGED" | grep -q '^backend/'; then
    echo "🔄 后端代码变化,重启后端(10秒)..."
    docker compose restart backend
elif echo "$CHANGED" | grep -qE '^frontend/|nginx\.conf|nginx-ssl\.conf'; then
    echo "⚡ 前端变化,重启 nginx(3秒)..."
    docker compose restart nginx
elif echo "$CHANGED" | grep -qE 'docker-compose\.yml'; then
    echo "🔄 编排变化,重启所有服务..."
    docker compose down && docker compose up -d
else
    echo "✓ 仅文档/配置变化,跳过重启"
fi
REMOTE_SCRIPT
fi

# === 完成 ===
echo -e "\n${GREEN}═══════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ 部署完成!${NC}"
echo -e "${GREEN}═══════════════════════════════════════${NC}"
echo -e ""
echo -e "${CYAN}🌐 访问地址:${NC}"
echo -e "   - http://110.42.217.122"
echo -e "   - HTTPS: 服务器上 mydomain 查看"
echo -e ""
echo -e "${YELLOW}💡 浏览器强刷新(Ctrl+F5)看效果${NC}"
echo -e ""
