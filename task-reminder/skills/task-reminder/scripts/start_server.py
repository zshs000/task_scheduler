"""
启动脚本 - 快速启动服务器
"""
import argparse
import json
import sys
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="启动任务调度服务")
    parser.add_argument("--daemon", action="store_true", help="后台运行（关闭窗口不影响服务）")
    args = parser.parse_args()

    print("=" * 60)
    print("任务调度系统 - 服务器启动")
    print("=" * 60)
    print()

    skill_root = Path(__file__).resolve().parent.parent
    project_dir = skill_root / "assets" / "project"
    venv_dir = skill_root / ".venv"
    venv_python = venv_dir / "Scripts" / "python.exe"
    requirements_path = skill_root / "requirements.txt"
    config_path = skill_root / "config" / "app_config.json"
    host = "127.0.0.1"
    port = "8000"
    if config_path.is_file():
        try:
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            host = str(cfg.get("host", host))
            port = str(cfg.get("port", port))
        except Exception:
            pass

    # 创建虚拟环境
    if not venv_python.is_file():
        print("正在创建虚拟环境...")
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)

    # 安装依赖
    if requirements_path.is_file():
        print("正在安装/更新依赖...")
        subprocess.run([str(venv_python), "-m", "pip", "install", "-r", str(requirements_path)], check=True)
    else:
        print("[ERROR] 找不到 requirements.txt")
        sys.exit(1)

    # 依赖检查
    try:
        subprocess.run(
            [str(venv_python), "-c", "import fastapi, uvicorn, apscheduler"],
            check=True
        )
        print("[OK] 依赖检查通过")
        print()
    except subprocess.CalledProcessError:
        print("[ERROR] 依赖检查失败，请检查安装输出")
        sys.exit(1)

    # 启动服务器
    print("正在启动服务器...")
    print(f"地址: http://{host}:{port}")
    print(f"API文档: http://{host}:{port}/docs")
    print()
    print("按 Ctrl+C 停止服务器")
    print("-" * 60)
    print()

    cmd = [
        str(venv_python), "-m", "uvicorn",
        "server.main:app",
        "--host", host,
        "--port", port
    ]

    try:
        if args.daemon:
            creationflags = 0
            if sys.platform.startswith("win"):
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
            proc = subprocess.Popen(cmd, cwd=str(project_dir), creationflags=creationflags)
            pid_path = skill_root / "server.pid"
            pid_path.write_text(str(proc.pid), encoding="utf-8")
            print(f"已后台启动，PID: {proc.pid}")
            print(f"访问地址: http://{host}:{port}")
            return

        subprocess.run(cmd, cwd=str(project_dir))
    except KeyboardInterrupt:
        print()
        print("服务器已停止")


if __name__ == "__main__":
    main()
