"""
审核历史数据存储 - SQLite with Connection Pool
"""
import sqlite3
import threading
from datetime import datetime
from typing import List, Optional, Dict
from pydantic import BaseModel
from contextlib import contextmanager


class Sample(BaseModel):
    """审核样本"""
    id: Optional[int] = None
    text: str
    label: int  # 0=pass, 1=violation
    category: Optional[str] = None
    created_at: Optional[str] = None


class ConnectionPool:
    """SQLite 连接池"""
    def __init__(self, db_path: str, max_connections: int = 10):
        self.db_path = db_path
        self.max_connections = max_connections
        self._pool = []
        self._lock = threading.Lock()
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表结构"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                label INTEGER NOT NULL,
                category TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    
    @contextmanager
    def get_connection(self):
        """获取连接（上下文管理器）"""
        conn = None
        with self._lock:
            if self._pool:
                conn = self._pool.pop()
            else:
                conn = sqlite3.connect(self.db_path, check_same_thread=False)
        
        try:
            yield conn
        finally:
            with self._lock:
                if len(self._pool) < self.max_connections:
                    self._pool.append(conn)
                else:
                    conn.close()
    
    def close_all(self):
        """关闭所有连接"""
        with self._lock:
            for conn in self._pool:
                conn.close()
            self._pool.clear()


# 全局连接池字典（每个数据库一个池）
_connection_pools: Dict[str, ConnectionPool] = {}
_pool_lock = threading.Lock()


def get_pool(db_path: str) -> ConnectionPool:
    """获取或创建连接池"""
    with _pool_lock:
        if db_path not in _connection_pools:
            _connection_pools[db_path] = ConnectionPool(db_path)
        return _connection_pools[db_path]


def cleanup_pools():
    """清理所有连接池（应用关闭时调用）"""
    with _pool_lock:
        for pool in _connection_pools.values():
            pool.close_all()
        _connection_pools.clear()


class SampleStorage:
    """样本存储管理"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.pool = get_pool(db_path)
    
    def save_sample(self, text: str, label: int, category: Optional[str] = None):
        """保存样本"""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO samples (text, label, category) VALUES (?, ?, ?)",
                (text, label, category)
            )
            conn.commit()
    
    def load_samples(self, max_samples: int = 20000) -> List[Sample]:
        """加载最新的样本"""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, text, label, category, created_at 
                FROM samples 
                ORDER BY created_at DESC 
                LIMIT ?
                """,
                (max_samples,)
            )
            rows = cursor.fetchall()
        
        return [
            Sample(
                id=row[0],
                text=row[1],
                label=row[2],
                category=row[3],
                created_at=row[4]
            )
            for row in rows
        ]
    
    def get_sample_count(self) -> int:
        """获取样本总数"""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM samples")
            count = cursor.fetchone()[0]
        return count
    
    def find_by_text(self, text: str) -> Optional[Sample]:
        """根据文本查找样本"""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, text, label, category, created_at FROM samples WHERE text = ? ORDER BY created_at DESC LIMIT 1",
                (text,)
            )
            row = cursor.fetchone()
        
        if row:
            return Sample(
                id=row[0],
                text=row[1],
                label=row[2],
                category=row[3],
                created_at=row[4]
            )
        return None