"""
任务调度模块
使用APScheduler管理定时任务
"""
import subprocess
import logging
from datetime import datetime
from pathlib import Path
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from .database import Database


logger = logging.getLogger(__name__)


class TaskScheduler:
    def __init__(self, database: Database):
        self.db = database
        self.scheduler = AsyncIOScheduler()
        self.scheduler.start()
        logger.info("调度器已启动")

    def load_tasks_from_db(self):
        """从数据库加载所有活跃任务"""
        tasks = self.db.get_active_tasks()
        loaded_count = 0

        for task in tasks:
            try:
                self.add_task(task, from_db=True)
                loaded_count += 1
            except Exception as e:
                logger.error(f"加载任务失败 {task['task_id']}: {e}")

        logger.info(f"从数据库加载了 {loaded_count} 个任务")
        return loaded_count

    def add_task(self, task_data: dict, from_db: bool = False):
        """
        添加任务到调度器

        Args:
            task_data: 任务数据
            from_db: 是否从数据库加载（True则不重复写入数据库）
        """
        task_id = task_data['task_id']
        task_type = task_data['task_type']
        script_path = task_data['script_path']
        script_args = task_data.get('script_args', [])

        # 如果不是从数据库加载，则先保存到数据库
        if not from_db:
            if not self.db.add_task(task_data):
                raise ValueError(f"任务ID已存在: {task_id}")

        # 构建触发器
        trigger = self._create_trigger(task_data)

        # 添加到调度器
        self.scheduler.add_job(
            func=self._execute_task,
            trigger=trigger,
            id=task_id,
            args=[task_id, script_path, script_args],
            replace_existing=True
        )

        logger.info(f"任务已添加: {task_id} ({task_type})")

    def _create_trigger(self, task_data: dict):
        """根据任务类型创建触发器"""
        task_type = task_data['task_type']

        if task_type == 'interval':
            seconds = task_data['interval_seconds']
            return IntervalTrigger(seconds=seconds)

        elif task_type == 'cron':
            cron_expr = task_data['cron_expression']
            parts = cron_expr.split()
            if len(parts) == 5:
                return CronTrigger(
                    minute=parts[0],
                    hour=parts[1],
                    day=parts[2],
                    month=parts[3],
                    day_of_week=parts[4]
                )
            else:
                raise ValueError(f"无效的cron表达式: {cron_expr}")

        elif task_type == 'date':
            execute_at = datetime.fromisoformat(task_data['execute_at'])
            return DateTrigger(run_date=execute_at)

        else:
            raise ValueError(f"不支持的任务类型: {task_type}")

    def _execute_task(self, task_id: str, script_path: str, script_args: list):
        """执行任务"""
        logger.info(f"开始执行任务: {task_id}")

        try:
            # 构建完整的脚本路径
            if not Path(script_path).is_absolute():
                script_path = Path(__file__).parent.parent / script_path

            # 执行脚本
            result = subprocess.run(
                ["python", str(script_path)] + script_args,
                capture_output=True,
                text=True,
                timeout=60
            )

            # 记录执行结果
            self.db.add_execution_log(
                task_id=task_id,
                return_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr
            )

            if result.returncode == 0:
                logger.info(f"任务执行成功: {task_id}")
            else:
                logger.error(f"任务执行失败: {task_id}, 返回码: {result.returncode}")
                logger.error(f"错误输出: {result.stderr}")

            # 如果是一次性任务（date类型），执行后标记为完成
            task = self.db.get_task(task_id)
            if task and task['task_type'] == 'date':
                self.remove_task(task_id)
                self.db.update_task_status(task_id, 'completed')
                logger.info(f"一次性任务已完成: {task_id}")

        except subprocess.TimeoutExpired:
            logger.error(f"任务执行超时: {task_id}")
            self.db.add_execution_log(task_id, -1, "", "执行超时")

        except Exception as e:
            logger.error(f"任务执行异常: {task_id}, {e}")
            self.db.add_execution_log(task_id, -1, "", str(e))

    def remove_task(self, task_id: str) -> bool:
        """移除任务"""
        try:
            self.scheduler.remove_job(task_id)
            logger.info(f"任务已移除: {task_id}")
            return True
        except Exception as e:
            logger.error(f"移除任务失败: {task_id}, {e}")
            return False

    def get_job_info(self, task_id: str):
        """获取任务信息"""
        job = self.scheduler.get_job(task_id)
        if job:
            return {
                'task_id': job.id,
                'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None
            }
        return None

    def get_all_jobs(self):
        """获取所有任务"""
        jobs = self.scheduler.get_jobs()
        return [
            {
                'task_id': job.id,
                'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None
            }
            for job in jobs
        ]

    def shutdown(self):
        """关闭调度器"""
        self.scheduler.shutdown()
        logger.info("调度器已关闭")
