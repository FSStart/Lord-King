#!/bin/bash
# Nexus AI 一键部署脚本 v2
# 用 scp 直接传文件,不依赖服务器 git pull

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
echo -e "${CYAN}   🚀 Nexus AI 一键部署 v2${NC}"
echo -e "${CYAN}═══════════════════════════════════════${NC}"

# === 1. 本地 git commit (可选,失败不阻塞) ===
echo -e "\n${YELLOW}[1/3]${NC} 本地 commit (可选,失败不影响)..."
git add . 2>/dev/null
if git diff --cached --quiet 2>/dev/null; then
    echo -e "  ${YELLOW}没有需要 commit 的修改${NC}"
else
    git commit -m "$MSG" 2>/dev/null && echo -e "  ${GREEN}✓ 已 commit${NC}" || echo -e "  ${YELLOW}commit 跳过${NC}"
    git push 2>/dev/null && echo -e "  ${GREEN}✓ 已 push${NC}" || echo -e "  ${YELLOW}push 失败(没关系,用 scp)${NC}"
fi

# === 2. 直接 scp 传文件(不依赖 git pull) ===
echo -e "\n${YELLOW}[2/3]${NC} 上传变更文件到服务器..."

CHANGED_FRONTEND=false
CHANGED_BACKEND=false
CHANGED_DEPS=false

# 检测最近 30 分钟修改的文件
RECENT_FILES=$(find frontend backend nginx.conf Dockerfile 2>/dev/null -type f -mmin -30 -not -path '*/node_modules/*' -not -path '*/.git/*' -not -path '*/__pycache__/*')

if [ -z "$RECENT_FILES" ]; then
    echo -e "  ${YELLOW}没检测到最近 30 分钟内的修改${NC}"
    echo -e "  ${YELLOW}使用全量同步前端 + 后端${NC}"
    
    scp frontend/index.html $SERVER:$PROJECT_PATH/frontend/index.html
    CHANGED_FRONTEND=true
    
    if [ -f "backend/app/main.py" ]; then
        scp backend/app/main.py $SERVER:$PROJECT_PATH/backend/app/main.py
        CHANGED_BACKEND=true
    fi
    
    if [ -f "backend/app/services/tools_service.py" ]; then
        scp backend/app/services/tools_service.py $SERVER:$PROJECT_PATH/backend/app/services/tools_service.py
    fi
else
    echo -e "  ${CYAN}变更文件:${NC}"
    echo "$RECENT_FILES" | while read file; do
        [ -z "$file" ] && continue
        echo "    - $file"
    done
    
    while IFS= read -r file; do
        [ -z "$file" ] && continue
        
        REMOTE_PATH="$PROJECT_PATH/$file"
        REMOTE_DIR=$(dirname "$REMOTE_PATH")
        
        ssh $SERVER "mkdir -p $REMOTE_DIR" 2>/dev/null
        scp "$file" "$SERVER:$REMOTE_PATH" > /dev/null 2>&1 && echo -e "    ${GREEN}✓${NC} $file"
        
        if [[ "$file" == frontend/* ]]; then
            CHANGED_FRONTEND=true
        elif [[ "$file" == backend/requirements.txt ]]; then
            CHANGED_DEPS=true
        elif [[ "$file" == backend/* ]]; then
            CHANGED_BACKEND=true
        elif [[ "$file" == nginx.conf ]]; then
            CHANGED_FRONTEND=true
        elif [[ "$file" == Dockerfile ]]; then
            CHANGED_DEPS=true
        fi
    done <<< "$RECENT_FILES"
fi

# === 3. 智能重启 ===
echo -e "\n${YELLOW}[3/3]${NC} 智能重启服务..."

if [ "$CHANGED_DEPS" = true ]; then
    echo "  🔨 依赖变化,重建后端镜像(3-5分钟)..."
    ssh $SERVER "cd $PROJECT_PATH && docker compose build backend && docker compose up -d"
elif [ "$CHANGED_BACKEND" = true ] && [ "$CHANGED_FRONTEND" = true ]; then
    echo "  🔄 前后端都变化,全部重启..."
    ssh $SERVER "cd $PROJECT_PATH && docker compose restart backend nginx"
elif [ "$CHANGED_BACKEND" = true ]; then
    echo "  🔄 后端代码变化,重启后端..."
    ssh $SERVER "cd $PROJECT_PATH && docker compose restart backend"
elif [ "$CHANGED_FRONTEND" = true ]; then
    echo "  ⚡ 前端变化,重启 nginx..."
    ssh $SERVER "cd $PROJECT_PATH && docker compose restart nginx"
else
    echo "  ✓ 没有需要重启的服务"
fi

# === 完成 ===
echo -e "\n${GREEN}═══════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ 部署完成!${NC}"
echo -e "${GREEN}═══════════════════════════════════════${NC}"
echo -e ""
echo -e "${CYAN}🌐 访问 HTTPS 域名:${NC} 服务器上 mydomain"
echo -e "${YELLOW}💡 浏览器强刷新 Ctrl+F5${NC}"
echo -e ""

# 更新 deploy.sh 时间戳作为下次检测基准
touch deploy.sh
