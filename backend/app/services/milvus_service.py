"""
Milvus 向量服务
- 优先用真实嵌入模型(DashScope text-embedding-v3,走 OpenAI 兼容接口),做真正的语义检索
- 没配 embedding key 时,降级到 hash 占位向量(结构上能跑,但召回靠运气)
两种模式用不同的 collection,维度不同,互不污染.
"""
from typing import List, Dict, Optional, Any
from pymilvus import MilvusClient, DataType
from datetime import datetime
from loguru import logger
from app.config import settings
import json
import os
import hashlib


class MilvusService:
    """Milvus 向量服务"""

    def __init__(self, db_path: str = "/app/data/milvus_lite.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.client = MilvusClient(uri=db_path)

        # 判断能否用真实嵌入: 配了 Qwen/DashScope key 就走 text-embedding-v3
        self.use_real_embed = bool(settings.USE_QWEN and settings.QWEN_API_KEY)
        self._embed_client = None
        if self.use_real_embed:
            try:
                from openai import AsyncOpenAI
                self._embed_client = AsyncOpenAI(
                    api_key=settings.QWEN_API_KEY,
                    base_url=settings.QWEN_API_URL,
                )
                self.dim = settings.EMBED_DIM
                self.collection_name = "memories_v3"
                logger.info(f"Milvus 使用真实嵌入模型: {settings.EMBED_MODEL} (dim={self.dim})")
            except Exception as e:
                logger.error(f"嵌入客户端初始化失败,降级到 hash 向量: {e}")
                self.use_real_embed = False

        if not self.use_real_embed:
            self.dim = 384
            self.collection_name = "memories"
            logger.warning("Milvus 使用 hash 占位向量(未配置 embedding,语义检索质量有限)")

        self._init_collection()
        logger.info(f"Milvus 服务已初始化: {db_path}")

    def _init_collection(self):
        """初始化集合"""
        try:
            if not self.client.has_collection(self.collection_name):
                schema = self.client.create_schema(auto_id=False, enable_dynamic_field=True)
                schema.add_field("id", DataType.VARCHAR, is_primary=True, max_length=64)
                schema.add_field("user_id", DataType.VARCHAR, max_length=64)
                schema.add_field("content", DataType.VARCHAR, max_length=8192)
                schema.add_field("vector", DataType.FLOAT_VECTOR, dim=self.dim)
                schema.add_field("metadata", DataType.VARCHAR, max_length=2048)
                schema.add_field("timestamp", DataType.INT64)

                self.client.create_collection(
                    collection_name=self.collection_name,
                    schema=schema
                )

                index_params = self.client.prepare_index_params()
                index_params.add_index(field_name="vector", metric_type="COSINE", index_type="FLAT")
                self.client.create_index(self.collection_name, index_params)

                logger.info(f"集合 {self.collection_name} 已创建")
        except Exception as e:
            logger.error(f"初始化集合失败: {e}")

    def _hash_vector(self, text: str) -> List[float]:
        """哈希占位向量(无 embedding 时的兜底,维度与 self.dim 对齐)"""
        vector = []
        for i in range(self.dim):
            h = hashlib.md5(f"{text}_{i}".encode()).hexdigest()
            vector.append((int(h[:8], 16) / 0xffffffff) * 2 - 1)
        return vector

    async def _embed(self, text: str) -> List[float]:
        """文本转向量: 优先真实嵌入模型,失败则降级到 hash(维度一致,不会写坏 collection)"""
        text = (text or "").strip()[:2000]
        if self._embed_client and text:
            try:
                resp = await self._embed_client.embeddings.create(
                    model=settings.EMBED_MODEL,
                    input=text,
                    dimensions=self.dim,
                )
                vec = resp.data[0].embedding
                if len(vec) == self.dim:
                    return vec
                logger.warning(f"嵌入维度不符 ({len(vec)} != {self.dim}),降级 hash")
            except Exception as e:
                logger.warning(f"嵌入调用失败,降级 hash: {e}")
        return self._hash_vector(text)

    async def insert_memory(self, user_id: str, content: str, metadata: Optional[Dict] = None) -> str:
        """插入记忆"""
        try:
            memory_id = hashlib.md5(
                f"{user_id}_{content}_{datetime.now().timestamp()}".encode()
            ).hexdigest()
            vector = await self._embed(content)

            self.client.insert(
                collection_name=self.collection_name,
                data=[{
                    "id": memory_id,
                    "user_id": user_id,
                    "content": content,
                    "vector": vector,
                    "metadata": json.dumps(metadata or {}),
                    "timestamp": int(datetime.now().timestamp())
                }]
            )
            return memory_id
        except Exception as e:
            logger.error(f"插入记忆失败: {e}")
            return ""

    async def search_memories(self, user_id: str, query: str, top_k: int = 5) -> List[Dict]:
        """搜索记忆"""
        try:
            query_vector = await self._embed(query)
            results = self.client.search(
                collection_name=self.collection_name,
                data=[query_vector],
                limit=top_k,
                output_fields=["content", "metadata", "timestamp"],
                filter=f'user_id == "{user_id}"'
            )

            memories = []
            if results and len(results) > 0:
                for hit in results[0]:
                    entity = hit.get("entity", {}) if isinstance(hit, dict) else {}
                    memories.append({
                        "content": entity.get("content", ""),
                        "metadata": json.loads(entity.get("metadata", "{}")),
                        "timestamp": entity.get("timestamp", 0),
                        "score": hit.get("distance", 0) if isinstance(hit, dict) else 0
                    })
            return memories
        except Exception as e:
            logger.error(f"搜索记忆失败: {e}")
            return []

    async def add_memory(self, user_id: str, content: str, metadata: Optional[Dict] = None) -> str:
        """insert_memory 的别名(兼容 main.py 旧调用)"""
        return await self.insert_memory(user_id, content, metadata)

    async def delete_user_memories(self, user_id: str):
        """删除用户所有记忆"""
        try:
            self.client.delete(
                collection_name=self.collection_name,
                filter=f'user_id == "{user_id}"'
            )
            logger.info(f"已删除用户 {user_id} 的所有记忆")
        except Exception as e:
            logger.error(f"删除记忆失败: {e}")

    def get_stats(self) -> Dict:
        """获取统计信息"""
        try:
            stats = self.client.get_collection_stats(self.collection_name)
            return {"collection": self.collection_name, "stats": stats}
        except Exception as e:
            return {"error": str(e)}


_milvus_service = None


def get_milvus_service(db_path: str = "/app/data/milvus_lite.db") -> MilvusService:
    """获取 Milvus 服务单例"""
    global _milvus_service
    if _milvus_service is None:
        _milvus_service = MilvusService(db_path=db_path)
    return _milvus_service
