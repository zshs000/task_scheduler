"""
FastAPI服务端
提供任务管理的REST API
"""
import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager
from .database import Database
from .scheduler import TaskScheduler


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# 全局变量
db = Database()
scheduler = TaskScheduler(db)


# 生命周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时加载任务
    logger.info("服务启动，加载任务...")
    scheduler.load_tasks_from_db()
    yield
    # 关闭时清理
    logger.info("服务关闭...")
    scheduler.shutdown()


app = FastAPI(
    title="任务调度系统",
    description="定时任务管理API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _load_app_config():
    for parent in Path(__file__).resolve().parents:
        config_path = parent / "config" / "app_config.json"
        if config_path.is_file():
            try:
                return json.loads(config_path.read_text(encoding="utf-8"))
            except Exception:
                return {}
    return {}


APP_CONFIG = _load_app_config()

# 静态文件目录
WEB_DIR = Path(__file__).parent.parent / "web"


# Web页面路由
@app.get("/web")
async def web_page():
    """返回Web管理页面"""
    return FileResponse(WEB_DIR / "index.html")


@app.get("/config")
async def get_config():
    """前端配置"""
    return {
        "api_base": APP_CONFIG.get("web_api_base") or APP_CONFIG.get("api_base") or "http://127.0.0.1:8000"
    }


# 数据模型
class TaskCreate(BaseModel):
    task_id: str = Field(..., description="任务唯一ID")
    task_type: str = Field(..., description="任务类型: interval/cron/date")
    interval_seconds: Optional[int] = Field(None, description="间隔秒数（interval类型）")
    cron_expression: Optional[str] = Field(None, description="Cron表达式（cron类型）")
    execute_at: Optional[str] = Field(None, description="执行时间（date类型）")
    script_path: str = Field(..., description="脚本路径")
    script_args: List[str] = Field(default_factory=list, description="脚本参数")


class TaskResponse(BaseModel):
    task_id: str
    task_type: str
    status: str
    script_path: str
    script_args: List[str]
    created_at: str
    next_run_time: Optional[str] = None


class ExecutionLog(BaseModel):
    id: int
    task_id: str
    executed_at: str
    return_code: int
    stdout: str
    stderr: str


# API路由
@app.get("/")
async def root():
    """根路径"""
    return {
        "service": "任务调度系统",
        "version": "1.0.0",
        "status": "running"
    }


@app.post("/tasks", response_model=dict)
async def create_task(task: TaskCreate):
    """创建新任务"""
    try:
        # 验证任务类型和参数
        if task.task_type == 'interval' and not task.interval_seconds:
            raise HTTPException(400, "interval类型需要提供interval_seconds")
        if task.task_type == 'cron' and not task.cron_expression:
            raise HTTPException(400, "cron类型需要提供cron_expression")
        if task.task_type == 'date' and not task.execute_at:
            raise HTTPException(400, "date类型需要提供execute_at")

        # 添加任务
        task_data = task.model_dump()
        scheduler.add_task(task_data)

        return {
            "success": True,
            "message": f"任务已创建: {task.task_id}",
            "task_id": task.task_id
        }

    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"创建任务失败: {e}")
        raise HTTPException(500, f"创建任务失败: {e}")


@app.get("/tasks", response_model=List[TaskResponse])
async def list_tasks():
    """获取所有任务列表"""
    try:
        tasks = db.get_all_tasks()

        # 添加下次运行时间
        for task in tasks:
            job_info = scheduler.get_job_info(task['task_id'])
            if job_info:
                task['next_run_time'] = job_info['next_run_time']

        return tasks

    except Exception as e:
        logger.error(f"获取任务列表失败: {e}")
        raise HTTPException(500, f"获取任务列表失败: {e}")


@app.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """获取单个任务详情"""
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(404, f"任务不存在: {task_id}")

    # 添加下次运行时间
    job_info = scheduler.get_job_info(task_id)
    if job_info:
        task['next_run_time'] = job_info['next_run_time']

    return task


@app.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    """删除任务"""
    try:
        # 从调度器移除
        scheduler.remove_task(task_id)

        # 从数据库删除
        if db.delete_task(task_id):
            return {
                "success": True,
                "message": f"任务已删除: {task_id}"
            }
        else:
            raise HTTPException(404, f"任务不存在: {task_id}")

    except Exception as e:
        logger.error(f"删除任务失败: {e}")
        raise HTTPException(500, f"删除任务失败: {e}")


@app.get("/tasks/{task_id}/history", response_model=List[ExecutionLog])
async def get_task_history(task_id: str):
    """获取任务执行历史"""
    try:
        history = db.get_execution_history(task_id)
        return history
    except Exception as e:
        logger.error(f"获取执行历史失败: {e}")
        raise HTTPException(500, f"获取执行历史失败: {e}")


@app.get("/history", response_model=List[ExecutionLog])
async def get_all_history():
    """获取所有任务执行历史"""
    try:
        history = db.get_execution_history()
        return history
    except Exception as e:
        logger.error(f"获取执行历史失败: {e}")
        raise HTTPException(500, f"获取执行历史失败: {e}")


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_jobs": len(scheduler.get_all_jobs())
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
@app.delete("/history", response_model=dict)
async def clear_history(task_id: Optional[str] = None):
    """清空执行历史"""
    try:
        deleted = db.clear_execution_history(task_id)
        return {
            "success": True,
            "deleted": deleted
        }
    except Exception as e:
        logger.error(f"清空执行历史失败: {e}")
        raise HTTPException(500, f"清空执行历史失败: {e}")
