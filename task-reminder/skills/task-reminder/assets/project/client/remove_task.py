"""
删除任务的客户端脚本
"""
import argparse
import requests
import sys


API_BASE_URL = "http://127.0.0.1:8000"


def remove_task(task_id):
    """删除任务"""
    try:
        response = requests.delete(f"{API_BASE_URL}/tasks/{task_id}", timeout=5)

        if response.status_code == 200:
            result = response.json()
            print(f"✓ {result['message']}")
            return True
        else:
            error = response.json()
            print(f"✗ 删除失败: {error.get('detail', '未知错误')}")
            return False

    except requests.exceptions.ConnectionError:
        print("✗ 错误: 无法连接到服务器")
        print("请确保服务器正在运行: python -m task_scheduler.server.main")
        return False
    except Exception as e:
        print(f"✗ 错误: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='删除定时任务')
    parser.add_argument('task_id', help='要删除的任务ID')

    args = parser.parse_args()

    success = remove_task(args.task_id)
    sys.exit(0 if success else 1)
