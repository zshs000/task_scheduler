"""
简化的提醒任务添加脚本
快速添加邮件提醒任务
"""
import argparse
import json
import re
import requests
import sys
from pathlib import Path
from datetime import datetime, timedelta


def _load_api_base():
    for parent in Path(__file__).resolve().parents:
        config_path = parent / "config" / "app_config.json"
        if config_path.is_file():
            try:
                cfg = json.loads(config_path.read_text(encoding="utf-8"))
                return cfg.get("web_api_base") or cfg.get("api_base")
            except Exception:
                return None
    return None


API_BASE_URL = _load_api_base() or "http://127.0.0.1:8000"
MAX_DAYS_AHEAD = 30


def parse_time(time_str: str) -> int:
    """解析时间字符串，如: 1h, 30m, 1h30m, 2d"""
    total_seconds = 0

    days = re.findall(r'(\d+)d', time_str)
    if days:
        total_seconds += int(days[0]) * 86400

    hours = re.findall(r'(\d+)h', time_str)
    if hours:
        total_seconds += int(hours[0]) * 3600

    minutes = re.findall(r'(\d+)m', time_str)
    if minutes:
        total_seconds += int(minutes[0]) * 60

    seconds = re.findall(r'(\d+)s', time_str)
    if seconds:
        total_seconds += int(seconds[0])

    return total_seconds


def _normalize_time_part(time_part: str):
    """解析时间部分: 支持 HH:MM[:SS] / H点 / H点半 / H点M分，并识别上午/下午"""
    if not time_part:
        return None

    part = time_part.strip()
    day_period = None
    for token in ["凌晨", "早上", "上午", "中午", "下午", "晚上", "傍晚"]:
        if token in part:
            day_period = token
            part = part.replace(token, "")

    match_hms = re.match(r'^(\d{1,2})(?::(\d{1,2}))?(?::(\d{1,2}))?$', part)
    if match_hms:
        hour = int(match_hms.group(1))
        minute = int(match_hms.group(2) or 0)
        second = int(match_hms.group(3) or 0)
    else:
        match_dot = re.match(r'^(\d{1,2})点(半|(\d{1,2})分)?$', part)
        if not match_dot:
            return None
        hour = int(match_dot.group(1))
        if match_dot.group(2) == "半":
            minute = 30
        elif match_dot.group(3):
            minute = int(match_dot.group(3))
        else:
            minute = 0
        second = 0

    if day_period in ["下午", "晚上", "傍晚"] and hour < 12:
        hour += 12
    if day_period in ["中午"] and 1 <= hour < 11:
        hour += 12

    if hour > 23 or minute > 59 or second > 59:
        return None

    return hour, minute, second


def parse_at_time(at_str: str) -> datetime:
    """解析指定时间：支持绝对时间与中文相对日期（明天/后天/X天后 + 时间）"""
    at_str = at_str.strip()

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(at_str, fmt)
        except ValueError:
            pass

    now = datetime.now()

    match_relative = re.match(r'^(明天|后天|(\d+)天后)\s*(.*)$', at_str)
    if match_relative:
        label = match_relative.group(1)
        days = 1 if label == "明天" else 2 if label == "后天" else int(match_relative.group(2))
        time_part = match_relative.group(3).strip()
        hms = _normalize_time_part(time_part)
        if hms is None:
            raise ValueError("相对日期需要具体时间，如: 明天 08:00 / 3天后 18:30")
        target_date = (now + timedelta(days=days)).date()
        return datetime(
            target_date.year, target_date.month, target_date.day,
            hms[0], hms[1], hms[2]
        )

    raise ValueError("不支持的时间格式")


def _validate_future_time(target_time: datetime):
    now = datetime.now()
    if target_time <= now:
        raise ValueError("时间必须晚于当前时间")
    if target_time - now > timedelta(days=MAX_DAYS_AHEAD):
        raise ValueError(f"时间不能超过未来 {MAX_DAYS_AHEAD} 天")


def add_reminder_by_seconds(seconds: int, content: str, task_id: str = None):
    """添加提醒任务（相对时间）"""
    if seconds <= 0:
        print("[ERROR] 无效的时间格式")
        print("支持格式: 1h, 30m, 1h30m, 2d, 30s")
        return False

    if not task_id:
        task_id = f"reminder_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    execute_at = (datetime.now() + timedelta(seconds=seconds)).isoformat()
    return _post_task(task_id, execute_at, content, f"{seconds}秒后")


def add_reminder_by_datetime(target_time: datetime, content: str, task_id: str = None):
    """添加提醒任务（绝对时间）"""
    try:
        _validate_future_time(target_time)
    except ValueError as e:
        print(f"[ERROR] {e}")
        return False

    if not task_id:
        task_id = f"reminder_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    execute_at = target_time.isoformat()
    return _post_task(task_id, execute_at, content, target_time.strftime("%Y-%m-%d %H:%M:%S"))


def _post_task(task_id: str, execute_at: str, content: str, time_desc: str):
    data = {
        'task_id': task_id,
        'task_type': 'date',
        'execute_at': execute_at,
        'script_path': 'scripts/send_email.py',
        'script_args': ['--content', content]
    }

    try:
        response = requests.post(f"{API_BASE_URL}/tasks", json=data, timeout=5)

        if response.status_code == 200:
            result = response.json()
            print("[OK] 提醒任务已创建")
            print(f"  任务ID: {result['task_id']}")
            print(f"  提醒时间: {time_desc}")
            print(f"  提醒内容: {content}")
            return True

        error = response.json()
        print(f"[ERROR] 创建失败: {error.get('detail', '未知错误')}")
        return False

    except requests.exceptions.ConnectionError:
        print("[ERROR] 无法连接到服务器")
        print("请确保服务器正在运行: py start_server.py")
        return False
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


def build_parser():
    parser = argparse.ArgumentParser(
        description="快速添加邮件提醒任务",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
时间格式:
  相对时间: 1h=1小时, 30m=30分钟, 1h30m=1小时30分钟, 2d=2天, 30s=30秒
  指定时间: YYYY-MM-DD HH:MM[:SS]
  相对日期: 明天/后天/X天后 + 时间（如: 明天 08:00）
        """
    )
    parser.add_argument("time_or_offset", nargs="?", help="相对时间，如: 1h30m")
    parser.add_argument("content", nargs="?", help="提醒内容")
    parser.add_argument("--at", dest="at_time", help="指定时间或相对日期")
    parser.add_argument("--id", dest="task_id", help="任务ID（可选）")
    return parser


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()

    if args.at_time:
        if not args.content:
            if args.time_or_offset:
                args.content = args.time_or_offset
            else:
                print("[ERROR] 请提供提醒内容")
                sys.exit(1)
        try:
            target_time = parse_at_time(args.at_time)
        except ValueError as e:
            print(f"[ERROR] {e}")
            sys.exit(1)

        success = add_reminder_by_datetime(target_time, args.content, args.task_id)
        sys.exit(0 if success else 1)

    if not args.time_or_offset or not args.content:
        parser.print_help()
        sys.exit(1)

    seconds = parse_time(args.time_or_offset)
    success = add_reminder_by_seconds(seconds, args.content, args.task_id)
    sys.exit(0 if success else 1)
