"""
快速测试脚本
验证系统是否正常工作
"""
import subprocess
import time
import sys
import requests


def test_server_connection():
    """测试服务器连接"""
    print("1. 测试服务器连接...")
    try:
        response = requests.get("http://127.0.0.1:8000/health", timeout=5)
        if response.status_code == 200:
            print("   ✓ 服务器运行正常")
            return True
        else:
            print("   ✗ 服务器响应异常")
            return False
    except requests.exceptions.ConnectionError:
        print("   ✗ 无法连接到服务器")
        print("   请先启动服务器: python start_server.py")
        return False


def test_add_task():
    """测试添加任务"""
    print("\n2. 测试添加任务...")
    result = subprocess.run([
        sys.executable, "client/add_task.py",
        "--id", "test_task",
        "--interval", "60",
        "--script", "scripts/send_email.py",
        "--args", "--content", "这是一个测试任务"
    ], capture_output=True, text=True)

    if result.returncode == 0:
        print("   ✓ 任务添加成功")
        print(f"   {result.stdout.strip()}")
        return True
    else:
        print("   ✗ 任务添加失败")
        print(f"   {result.stderr.strip()}")
        return False


def test_list_tasks():
    """测试查看任务"""
    print("\n3. 测试查看任务...")
    result = subprocess.run([
        sys.executable, "client/list_tasks.py"
    ], capture_output=True, text=True)

    if result.returncode == 0:
        print("   ✓ 任务列表获取成功")
        print(f"   {result.stdout.strip()}")
        return True
    else:
        print("   ✗ 任务列表获取失败")
        return False


def test_remove_task():
    """测试删除任务"""
    print("\n4. 测试删除任务...")
    result = subprocess.run([
        sys.executable, "client/remove_task.py", "test_task"
    ], capture_output=True, text=True)

    if result.returncode == 0:
        print("   ✓ 任务删除成功")
        print(f"   {result.stdout.strip()}")
        return True
    else:
        print("   ✗ 任务删除失败")
        return False


def main():
    print("=" * 60)
    print("任务调度系统 - 功能测试")
    print("=" * 60)

    # 测试服务器连接
    if not test_server_connection():
        sys.exit(1)

    # 测试添加任务
    if not test_add_task():
        sys.exit(1)

    # 等待一下
    time.sleep(1)

    # 测试查看任务
    if not test_list_tasks():
        sys.exit(1)

    # 测试删除任务
    if not test_remove_task():
        sys.exit(1)

    print("\n" + "=" * 60)
    print("✓ 所有测试通过！系统运行正常")
    print("=" * 60)


if __name__ == "__main__":
    main()
