"""
数据库操作模块
使用SQLite存储任务信息和执行历史
"""
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional


class Database:
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent / "data" / "tasks.db"
        self.db_path = db_path
        self.init_database()

    def get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_database(self):
        """初始化数据库表"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # 任务表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                task_type TEXT NOT NULL,
                interval_seconds INTEGER,
                cron_expression TEXT,
                execute_at TEXT,
                script_path TEXT NOT NULL,
                script_args TEXT,
                status TEXT DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # 执行历史表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS execution_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                executed_at TEXT NOT NULL,
                return_code INTEGER,
                stdout TEXT,
                stderr TEXT,
                FOREIGN KEY (task_id) REFERENCES tasks(task_id)
            )
        """)

        conn.commit()
        conn.close()

    def add_task(self, task_data: Dict) -> bool:
        """添加任务"""
        conn = self.get_connection()
        cursor = conn.cursor()

        now = datetime.now().isoformat()

        try:
            cursor.execute("""
                INSERT INTO tasks (
                    task_id, task_type, interval_seconds, cron_expression,
                    execute_at, script_path, script_args, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task_data['task_id'],
                task_data['task_type'],
                task_data.get('interval_seconds'),
                task_data.get('cron_expression'),
                task_data.get('execute_at'),
                task_data['script_path'],
                json.dumps(task_data.get('script_args', [])),
                'active',
                now,
                now
            ))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def get_task(self, task_id: str) -> Optional[Dict]:
        """获取单个任务"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return self._row_to_dict(row)
        return None

    def get_all_tasks(self) -> List[Dict]:
        """获取所有任务"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM tasks ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_dict(row) for row in rows]

    def get_active_tasks(self) -> List[Dict]:
        """获取所有活跃任务"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM tasks WHERE status = 'active'")
        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_dict(row) for row in rows]

    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()

        return deleted

    def update_task_status(self, task_id: str, status: str) -> bool:
        """更新任务状态"""
        conn = self.get_connection()
        cursor = conn.cursor()

        now = datetime.now().isoformat()
        cursor.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ?",
            (status, now, task_id)
        )
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()

        return updated

    def add_execution_log(self, task_id: str, return_code: int,
                         stdout: str, stderr: str):
        """添加执行日志"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO execution_history (
                task_id, executed_at, return_code, stdout, stderr
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            task_id,
            datetime.now().isoformat(),
            return_code,
            stdout,
            stderr
        ))
        conn.commit()
        conn.close()

    def get_execution_history(self, task_id: str = None) -> List[Dict]:
        """获取执行历史"""
        conn = self.get_connection()
        cursor = conn.cursor()

        if task_id:
            cursor.execute("""
                SELECT * FROM execution_history
                WHERE task_id = ?
                ORDER BY executed_at DESC
            """, (task_id,))
        else:
            cursor.execute("""
                SELECT * FROM execution_history
                ORDER BY executed_at DESC
            """)

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def clear_execution_history(self, task_id: Optional[str] = None) -> int:
        """清空执行历史，返回删除条数"""
        conn = self.get_connection()
        cursor = conn.cursor()

        if task_id:
            cursor.execute("DELETE FROM execution_history WHERE task_id = ?", (task_id,))
        else:
            cursor.execute("DELETE FROM execution_history")

        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted

    def _row_to_dict(self, row) -> Dict:
        """将数据库行转换为字典"""
        data = dict(row)
        if data.get('script_args'):
            data['script_args'] = json.loads(data['script_args'])
        return data
