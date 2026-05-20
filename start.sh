#!/bin/bash
# Nexus AI 一键启动脚本

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo -e "${BLUE}     Nexus AI - 部署脚本${NC}"
echo -e "${BLUE}═══════════════════════════════════════${NC}\n"

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker 未安装${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker 已安装${NC}"

# 检查 .env
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo -e "${YELLOW}⚠ 已创建 .env (使用默认值,可后续编辑)${NC}"
    else
        echo -e "${RED}✗ 找不到 .env.example${NC}"
        exit 1
    fi
fi
echo -e "${GREEN}✓ .env 文件就绪${NC}\n"

# 启动
echo -e "${BLUE}🚀 启动服务 (首次构建需 5-10 分钟)...${NC}\n"
docker compose up -d --build

echo -e "\n${BLUE}⏳ 等待服务启动...${NC}"
sleep 10

# 检查状态
if docker compose ps | grep -q "Up\|running"; then
    SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')

    echo -e "\n${GREEN}═══════════════════════════════════════${NC}"
    echo -e "${GREEN}  🎉 Nexus AI 部署成功!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════${NC}"
    echo -e ""
    echo -e "  ${BLUE}🌐 访问地址:${NC}"
    echo -e "     - 本地: http://localhost"
    echo -e "     - 公网: http://$SERVER_IP"
    echo -e ""
    echo -e "  ${BLUE}📡 API:${NC}"
    echo -e "     - 健康检查: http://$SERVER_IP/health"
    echo -e "     - 统计: http://$SERVER_IP/stats"
    echo -e ""
    echo -e "  ${BLUE}🔧 管理:${NC}"
    echo -e "     - 查看日志: docker compose logs -f"
    echo -e "     - 停止服务: docker compose down"
    echo -e "     - 重启服务: docker compose restart"
    echo -e ""
else
    echo -e "\n${RED}✗ 服务启动可能有问题${NC}"
    echo -e "${YELLOW}查看日志: docker compose logs backend${NC}"
fi
