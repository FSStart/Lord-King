# Nexus AI - 私人智能助手 👑

支持语音唤醒的 AI 助手,唤醒词:**"LordKing"**

## 🚀 快速部署

### 服务器要求
- Ubuntu 20.04+
- 4 核 4G 内存
- 已安装 Docker 和 docker-compose

### 部署步骤

```bash
# 1. 克隆仓库
git clone <你的仓库URL>
cd nexus-ai

# 2. 配置环境变量(可选,有默认值)
cp .env.example .env
nano .env  # 编辑配置

# 3. 一键启动
chmod +x start.sh
./start.sh
```

预计 **5-10 分钟**完成构建。

## 🌐 访问

- 前端: `http://你的服务器IP`
- 健康检查: `http://你的服务器IP/health`
- 统计信息: `http://你的服务器IP/stats`

## 🎤 语音功能

1. **必须使用 HTTPS 或 localhost** (浏览器麦克风权限要求)
2. 点击右上角"耳朵"图标开启唤醒词
3. 说 "LordKing" 唤醒
4. 等"叮"一声后说出指令

## ⚙️ 配置

编辑 `.env` 文件:

```bash
# 主要配置
CLAUDE_API_KEY=sk-ant-xxx        # Claude API Key
USE_QWEN=false                    # 切换到 Qwen

# Qwen 配置(可选)
QWEN_API_KEY=sk-xxx               # 通义千问 API Key
QWEN_MODEL=qwen-max-latest
```

切换到 Qwen:
```bash
# 修改 .env
USE_QWEN=true
QWEN_API_KEY=你的Qwen Key

# 重启
docker compose restart backend
```

## 🔧 常用命令

```bash
# 查看日志
docker compose logs -f backend

# 重启服务
docker compose restart

# 停止服务
docker compose down

# 完全重建
docker compose down
docker compose build --no-cache
docker compose up -d
```

## 📦 项目结构

```
nexus-ai/
├── backend/
│   ├── app/
│   │   ├── services/
│   │   │   ├── milvus_service.py    # 向量数据库
│   │   │   └── llm_service.py       # LLM 服务(支持 Claude/Qwen)
│   │   ├── config.py                # 配置
│   │   └── main.py                  # 主入口
│   └── requirements.txt
├── frontend/
│   └── index.html                   # 语音版前端
├── Dockerfile
├── docker-compose.yml
├── nginx.conf
└── start.sh
```

## 🆘 故障排查

### 后端启动失败
```bash
docker compose logs backend | tail -30
```

### 网页无法访问
1. 检查防火墙开放 80 端口
2. 检查容器状态: `docker compose ps`

### 语音不能用
- 必须 HTTPS 或 localhost
- 用 Chrome/Edge 浏览器
- 允许麦克风权限

## 📝 License

MIT
