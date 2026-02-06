"""
查看任务列表的客户端脚本
"""
import argparse
import requests
import sys
from datetime import datetime


API_BASE_URL = "http://127.0.0.1:8000"


def list_tasks(show_history=False, task_id=None):
    """列出所有任务"""
    try:
        if task_id:
            # 查看单个任务详情
            response = requests.get(f"{API_BASE_URL}/tasks/{task_id}", timeout=5)
            if response.status_code == 200:
                task = response.json()
                print_task_detail(task)

                if show_history:
                    print("\n执行历史:")
                    print("-" * 80)
                    show_task_history(task_id)
                return True
            else:
                print(f"✗ 任务不存在: {task_id}")
                return False
        else:
            # 查看所有任务
            response = requests.get(f"{API_BASE_URL}/tasks", timeout=5)

            if response.status_code == 200:
                tasks = response.json()

                if not tasks:
                    print("暂无任务")
                    return True

                print(f"共 {len(tasks)} 个任务:\n")
                print("-" * 100)
                print(f"{'任务ID':<20} {'类型':<10} {'状态':<10} {'下次运行':<25} {'脚本':<30}")
                print("-" * 100)

                for task in tasks:
                    next_run = task.get('next_run_time', 'N/A')
                    if next_run and next_run != 'N/A':
                        try:
                            dt = datetime.fromisoformat(next_run)
                            next_run = dt.strftime('%Y-%m-%d %H:%M:%S')
                        except:
                            pass

                    print(f"{task['task_id']:<20} {task['task_type']:<10} {task['status']:<10} {next_run:<25} {task['script_path']:<30}")

                print("-" * 100)

                if show_history:
                    print("\n最近执行历史:")
                    print("-" * 100)
                    show_all_history()

                return True
            else:
                print(f"✗ 获取任务列表失败")
                return False

    except requests.exceptions.ConnectionError:
        print("✗ 错误: 无法连接到服务器")
        print("请确保服务器正在运行: python -m task_scheduler.server.main")
        return False
    except Exception as e:
        print(f"✗ 错误: {e}")
        return False


def print_task_detail(task):
    """打印任务详情"""
    print(f"任务ID: {task['task_id']}")
    print(f"类型: {task['task_type']}")
    print(f"状态: {task['status']}")
    print(f"脚本: {task['script_path']}")

    if task.get('script_args'):
        print(f"参数: {' '.join(task['script_args'])}")

    if task['task_type'] == 'interval':
        print(f"间隔: {task.get('interval_seconds')}秒")
    elif task['task_type'] == 'cron':
        print(f"Cron: {task.get('cron_expression')}")
    elif task['task_type'] == 'date':
        print(f"执行时间: {task.get('execute_at')}")

    if task.get('next_run_time'):
        dt = datetime.fromisoformat(task['next_run_time'])
        print(f"下次运行: {dt.strftime('%Y-%m-%d %H:%M:%S')}")

    print(f"创建时间: {task['created_at']}")


def show_task_history(task_id):
    """显示任务执行历史"""
    try:
        response = requests.get(f"{API_BASE_URL}/tasks/{task_id}/history", timeout=5)

        if response.status_code == 200:
            history = response.json()

            if not history:
                print("  暂无执行记录")
                return

            for record in history:
                executed_at = datetime.fromisoformat(record['executed_at']).strftime('%Y-%m-%d %H:%M:%S')
                status = "✓ 成功" if record['return_code'] == 0 else f"✗ 失败({record['return_code']})"
                print(f"  [{executed_at}] {status}")

                if record['stdout']:
                    print(f"    输出: {record['stdout'][:100]}")
                if record['stderr']:
                    print(f"    错误: {record['stderr'][:100]}")
                print()

    except Exception as e:
        print(f"  获取历史失败: {e}")


def show_all_history():
    """显示所有任务的执行历史"""
    try:
        response = requests.get(f"{API_BASE_URL}/history", timeout=5)

        if response.status_code == 200:
            history = response.json()

            if not history:
                print("  暂无执行记录")
                return

            for record in history:
                executed_at = datetime.fromisoformat(record['executed_at']).strftime('%Y-%m-%d %H:%M:%S')
                status = "✓" if record['return_code'] == 0 else "✗"
                print(f"  {status} [{executed_at}] {record['task_id']}")

    except Exception as e:
        print(f"  获取历史失败: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='查看任务列表')
    parser.add_argument('--id', help='查看指定任务的详情')
    parser.add_argument('--history', action='store_true', help='显示执行历史')

    args = parser.parse_args()

    success = list_tasks(show_history=args.history, task_id=args.id)
    sys.exit(0 if success else 1)
