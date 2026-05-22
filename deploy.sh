#!/bin/bash
# Nexus AI 一键部署脚本

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# ===== 配置 =====
SERVER="root@110.42.217.122"
PROJECT_PATH="/root/Lord-King"

# 提交信息(没传就用默认)
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
    echo -e "\n${YELLOW}[2/4]${NC} 检查远程是否需要同步..."
    git push 2>/dev/null
fi

# === 3. 服务器拉取 ===
echo -e "\n${YELLOW}[3/4]${NC} 服务器拉取代码..."
PULL_OUTPUT=$(ssh $SERVER "cd $PROJECT_PATH && git pull" 2>&1)
echo "$PULL_OUTPUT"

if echo "$PULL_OUTPUT" | grep -q "Already up to date"; then
    echo -e "${YELLOW}  ⓘ 服务器代码已是最新${NC