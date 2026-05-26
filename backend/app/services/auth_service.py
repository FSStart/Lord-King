"""
用户认证服务
- 注册 / 登录 / JWT
- 用 PostgreSQL 存用户
"""
import os
import re
from datetime import datetime, timedelta
from typing import Optional
import asyncpg
import bcrypt
import jwt
from loguru import logger
from pydantic import BaseModel


# JWT 配置
JWT_SECRET = os.getenv("JWT_SECRET", "lord-king-secret-change-me-in-production-2026")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 7


# ============ 数据模型 ============

class UserRegister(BaseModel):
    username: str
    password: str
    nickname: Optional[str] = None


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str
    nickname: Optional[str] = None
    expires_in: int = JWT_EXPIRE_DAYS * 86400


# ============ Auth Service ============

class AuthService:
    def __init__(self):
        self.pool = None

    async def init_db(self):
        """初始化数据库连接和用户表"""
        try:
            postgres_host = os.getenv("POSTGRES_HOST", "postgres")
            postgres_port = int(os.getenv("POSTGRES_PORT", "5432"))
            postgres_user = os.getenv("POSTGRES_USER", "postgres")
            postgres_password = os.getenv("POSTGRES_PASSWORD", "MyNexus2026")
            postgres_db = os.getenv("POSTGRES_DB", "postgres")

            self.pool = await asyncpg.create_pool(
                host=postgres_host,
                port=postgres_port,
                user=postgres_user,
                password=postgres_password,
                database=postgres_db,
                min_size=1,
                max_size=10
            )

            # 创建用户表
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        username VARCHAR(50) UNIQUE NOT NULL,
                        password_hash VARCHAR(255) NOT NULL,
                        nickname VARCHAR(50),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_login TIMESTAMP,
                        settings JSONB DEFAULT '{}'::jsonb
                    )
                """)
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")

            logger.info("OK Auth DB ready - PostgreSQL")
            return True

        except Exception as ex:
            logger.error("Auth DB init failed: " + str(ex))
            return False

    async def close(self):
        if self.pool:
            await self.pool.close()

    # ============ 密码工具 ============

    @staticmethod
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        try:
            return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
        except Exception:
            return False

    # ============ JWT 工具 ============

    @staticmethod
    def create_token(user_id: int, username: str) -> str:
        payload = {
            "user_id": user_id,
            "username": username,
            "exp": datetime.utcnow() + timedelta(days=JWT_EXPIRE_DAYS),
            "iat": datetime.utcnow()
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    @staticmethod
    def verify_token(token: str) -> Optional[dict]:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError:
            logger.warning("Invalid token")
            return None

    # ============ 业务方法 ============

    async def register(self, username: str, password: str, nickname: Optional[str] = None):
        """注册新用户"""
        # 验证用户名
        if not username or len(username) < 3 or len(username) > 20:
            return {"success": False, "error": "用户名长度需 3-20 个字符"}

        if not re.match(r"^[a-zA-Z0-9_]+$", username):
            return {"success": False, "error": "用户名只能包含字母、数字、下划线"}

        if len(password) < 6:
            return {"success": False, "error": "密码至少 6 个字符"}

        if not self.pool:
            return {"success": False, "error": "数据库未就绪"}

        try:
            async with self.pool.acquire() as conn:
                # 检查重复
                exists = await conn.fetchval(
                    "SELECT id FROM users WHERE username = $1", username
                )
                if exists:
                    return {"success": False, "error": "用户名已存在"}

                # 创建用户
                password_hash = self.hash_password(password)
                actual_nickname = nickname if nickname else username

                user_id = await conn.fetchval(
                    """INSERT INTO users (username, password_hash, nickname)
                       VALUES ($1, $2, $3) RETURNING id""",
                    username, password_hash, actual_nickname
                )

                token = self.create_token(user_id, username)
                logger.info("New user registered: " + username + " (id=" + str(user_id) + ")")

                return {
                    "success": True,
                    "access_token": token,
                    "user_id": str(user_id),
                    "username": username,
                    "nickname": actual_nickname
                }
        except Exception as ex:
            logger.error("Register failed: " + str(ex))
            return {"success": False, "error": "注册失败: " + str(ex)}

    async def login(self, username: str, password: str):
        """登录"""
        if not self.pool:
            return {"success": False, "error": "数据库未就绪"}

        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT id, username, password_hash, nickname FROM users WHERE username = $1",
                    username
                )
                if not row:
                    return {"success": False, "error": "用户不存在"}

                if not self.verify_password(password, row["password_hash"]):
                    return {"success": False, "error": "密码错误"}

                # 更新最后登录时间
                await conn.execute(
                    "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = $1",
                    row["id"]
                )

                token = self.create_token(row["id"], row["username"])
                logger.info("User logged in: " + row["username"])

                return {
                    "success": True,
                    "access_token": token,
                    "user_id": str(row["id"]),
                    "username": row["username"],
                    "nickname": row["nickname"]
                }
        except Exception as ex:
            logger.error("Login failed: " + str(ex))
            return {"success": False, "error": "登录失败"}

    async def get_user(self, user_id: int):
        """获取用户信息"""
        if not self.pool:
            return None
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT id, username, nickname, created_at, settings FROM users WHERE id = $1",
                    user_id
                )
                if not row:
                    return None
                return {
                    "user_id": str(row["id"]),
                    "username": row["username"],
                    "nickname": row["nickname"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    "settings": row["settings"] or {}
                }
        except Exception as ex:
            logger.error("Get user failed: " + str(ex))
            return None

    async def update_settings(self, user_id: int, settings: dict):
        """更新用户设置"""
        if not self.pool:
            return False
        try:
            async with self.pool.acquire() as conn:
                import json
                await conn.execute(
                    "UPDATE users SET settings = $1 WHERE id = $2",
                    json.dumps(settings), user_id
                )
                return True
        except Exception as ex:
            logger.error("Update settings failed: " + str(ex))
            return False

    async def change_password(self, user_id: int, old_password: str, new_password: str):
        """修改密码"""
        if not self.pool:
            return {"success": False, "error": "数据库未就绪"}

        if len(new_password) < 6:
            return {"success": False, "error": "新密码至少 6 个字符"}

        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT password_hash FROM users WHERE id = $1", user_id
                )
                if not row:
                    return {"success": False, "error": "用户不存在"}

                if not self.verify_password(old_password, row["password_hash"]):
                    return {"success": False, "error": "原密码错误"}

                new_hash = self.hash_password(new_password)
                await conn.execute(
                    "UPDATE users SET password_hash = $1 WHERE id = $2",
                    new_hash, user_id
                )
                return {"success": True}
        except Exception as ex:
            logger.error("Change password failed: " + str(ex))
            return {"success": False, "error": str(ex)}


# 全局实例
_auth_service = None


def get_auth_service():
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service
