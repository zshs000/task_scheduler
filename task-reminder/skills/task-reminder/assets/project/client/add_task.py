"""
添加定时任务的客户端脚本
"""
import argparse
import requests
import sys
from datetime import datetime, timedelta


API_BASE_URL = "http://127.0.0.1:8000"


def add_task(task_id, task_type, script_path, script_args,
             interval_seconds=None, cron_expression=None, execute_at=None):
    """添加任务"""

    # 构建请求数据
    data = {
        "task_id": task_id,
        "task_type": task_type,
        "script_path": script_path,
        "script_args": script_args
    }

    if task_type == 'interval':
        data['interval_seconds'] = interval_seconds
    elif task_type == 'cron':
        data['cron_expression'] = cron_expression
    elif task_type == 'date':
        data['execute_at'] = execute_at

    try:
        response = requests.post(f"{API_BASE_URL}/tasks", json=data, timeout=5)

        if response.status_code == 200:
            result = response.json()
            print(f"✓ 任务创建成功: {result['task_id']}")
            print(f"  类型: {task_type}")
            if task_type == 'interval':
                print(f"  间隔: {interval_seconds}秒")
            elif task_type == 'cron':
                print(f"  Cron: {cron_expression}")
            elif task_type == 'date':
                print(f"  执行时间: {execute_at}")
            print(f"  脚本: {script_path}")
            if script_args:
                print(f"  参数: {' '.join(script_args)}")
            return True
        else:
            error = response.json()
            print(f"✗ 创建失败: {error.get('detail', '未知错误')}")
            return False

    except requests.exceptions.ConnectionError:
        print("✗ 错误: 无法连接到服务器")
        print("请确保服务器正在运行: python -m task_scheduler.server.main")
        return False
    except Exception as e:
        print(f"✗ 错误: {e}")
        return False


def parse_time_offset(offset_str):
    """
    解析时间偏移量
    支持格式: 1h, 30m, 1h30m, 2d
    """
    import re

    total_seconds = 0

    # 匹配天数
    days = re.findall(r'(\d+)d', offset_str)
    if days:
        total_seconds += int(days[0]) * 86400

    # 匹配小时
    hours = re.findall(r'(\d+)h', offset_str)
    if hours:
        total_seconds += int(hours[0]) * 3600

    # 匹配分钟
    minutes = re.findall(r'(\d+)m', offset_str)
    if minutes:
        total_seconds += int(minutes[0]) * 60

    # 匹配秒
    seconds = re.findall(r'(\d+)s', offset_str)
    if seconds:
        total_seconds += int(seconds[0])

    return total_seconds


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='添加定时任务',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 每30秒执行一次
  python add_task.py --id remind1 --interval 30 --script scripts/send_email.py --args "--content" "测试提醒"

  # 1小时后执行一次
  python add_task.py --id remind2 --after 1h --script scripts/send_email.py --args "--content" "1小时后的提醒"

  # 每天早上8点执行
  python add_task.py --id daily --cron "0 8 * * *" --script scripts/send_email.py --args "--content" "早安提醒"

  # 指定时间执行
  python add_task.py --id meeting --at "2026-02-05 15:00:00" --script scripts/send_email.py --args "--content" "会议提醒"
        """
    )

    parser.add_argument('--id', required=True, help='任务ID（唯一标识）')
    parser.add_argument('--script', required=True, help='要执行的脚本路径')
    parser.add_argument('--args', nargs='*', default=[], help='脚本参数')

    # 任务类型（互斥）
    type_group = parser.add_mutually_exclusive_group(required=True)
    type_group.add_argument('--interval', type=int, help='间隔秒数（周期性任务）')
    type_group.add_argument('--after', type=str, help='多久后执行（一次性任务），如: 1h, 30m, 1h30m')
    type_group.add_argument('--at', type=str, help='指定时间执行（一次性任务），格式: YYYY-MM-DD HH:MM:SS')
    type_group.add_argument('--cron', type=str, help='Cron表达式（周期性任务）')

    args = parser.parse_args()

    # 确定任务类型和参数
    if args.interval:
        task_type = 'interval'
        interval_seconds = args.interval
        cron_expression = None
        execute_at = None

    elif args.after:
        task_type = 'date'
        interval_seconds = None
        cron_expression = None
        offset_seconds = parse_time_offset(args.after)
        if offset_seconds == 0:
            print("✗ 错误: 无效的时间偏移量格式")
            print("支持格式: 1h, 30m, 1h30m, 2d")
            sys.exit(1)
        execute_at = (datetime.now() + timedelta(seconds=offset_seconds)).isoformat()

    elif args.at:
        task_type = 'date'
        interval_seconds = None
        cron_expression = None
        try:
            execute_at = datetime.fromisoformat(args.at).isoformat()
        except ValueError:
            print("✗ 错误: 无效的时间格式")
            print("正确格式: YYYY-MM-DD HH:MM:SS")
            sys.exit(1)

    elif args.cron:
        task_type = 'cron'
        interval_seconds = None
        cron_expression = args.cron
        execute_at = None

    # 添加任务
    success = add_task(
        task_id=args.id,
        task_type=task_type,
        script_path=args.script,
        script_args=args.args,
        interval_seconds=interval_seconds,
        cron_expression=cron_expression,
        execute_at=execute_at
    )

    sys.exit(0 if success else 1)
