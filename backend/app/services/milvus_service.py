"""
Milvus 向量服务 - 简化版
用 hash 生成向量,不依赖 sentence-transformers,避免拉取 PyTorch/CUDA
后期可以替换为真实的嵌入模型
"""
from typing import List, Dict, Optional, Any
from pymilvus import MilvusClient, DataType
from datetime import datetime
from loguru import logger
import json
import os
import hashlib


class MilvusService:
    """Milvus 向量服务"""

    def __init__(self, db_path: str = "/app/data/milvus_lite.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.client = MilvusClient(uri=db_path)
        self.collection_name = "memories"
        self.dim = 384
        self.embedding_model = None
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

    def _text_to_vector(self, text: str) -> List[float]:
        """简单的文本转向量(用哈希,占位符)"""
        vector = []
        for i in range(self.dim):
            h = hashlib.md5(f"{text}_{i}".encode()).hexdigest()
            vector.append((int(h[:8], 16) / 0xffffffff) * 2 - 1)
        return vector

    async def insert_memory(self, user_id: str, content: str, metadata: Optional[Dict] = None) -> str:
        """插入记忆"""
        try:
            memory_id = hashlib.md5(
                f"{user_id}_{content}_{datetime.now().timestamp()}".encode()
            ).hexdigest()
            vector = self._text_to_vector(content)

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
            query_vector = self._text_to_vector(query)
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
