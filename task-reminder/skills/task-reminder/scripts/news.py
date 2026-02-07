"""
新闻 CLI 入口
支持手动触发抓取推送 / 注册定时任务
"""
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

import requests


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


def cmd_now(args):
    """立即抓取并推送新闻"""
    # 定位 news_crawler.py
    skill_root = None
    for parent in Path(__file__).resolve().parents:
        if (parent / "assets" / "project" / "scripts" / "news_crawler.py").is_file():
            skill_root = parent
            break

    if not skill_root:
        print("[ERROR] 找不到 news_crawler.py")
        sys.exit(1)

    # 将 scripts 目录加入 path 以便导入
    scripts_dir = str(skill_root / "assets" / "project" / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    from news_crawler import crawl_news, push_news, format_digest_plain, format_digest_markdown

    print("[INFO] 开始抓取新闻...")
    items = crawl_news(sources_filter=args.sources)

    if not items:
        print("[INFO] 没有新的新闻")
        return

    print(f"[INFO] 共获取 {len(items)} 条新闻")

    if args.no_push:
        print("\n--- 预览 ---")
        print(format_digest_plain(items))
    else:
        print("[INFO] 正在推送...")
        success = push_news(items, channels=args.channels)
        if success:
            print("[OK] 新闻推送完成")
        else:
            print("[ERROR] 新闻推送失败")
            sys.exit(1)


def cmd_schedule(args):
    """注册定时新闻推送任务到服务器"""
    cron_expr = args.cron
    channels = args.channels

    # 构建脚本参数
    script_args = []
    if channels:
        script_args.extend(["--channels"] + channels)

    task_id = f"news_schedule_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    data = {
        "task_id": task_id,
        "task_type": "cron",
        "cron_expression": cron_expr,
        "script_path": "scripts/news_crawler.py",
        "script_args": script_args,
    }

    try:
        response = requests.post(f"{API_BASE_URL}/tasks", json=data, timeout=5)

        if response.status_code == 200:
            result = response.json()
            print("[OK] 定时新闻任务已创建")
            print(f"  任务ID: {result['task_id']}")
            print(f"  Cron: {cron_expr}")
            if channels:
                print(f"  渠道: {', '.join(channels)}")
            print(f"\n可在 Web UI 查看任务状态")
            return

        error = response.json()
        print(f"[ERROR] 创建失败: {error.get('detail', '未知错误')}")
        sys.exit(1)

    except requests.exceptions.ConnectionError:
        print("[ERROR] 无法连接到服务器")
        print("请确保服务器正在运行: py start_server.py")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="新闻推送 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python news.py now                          立即抓取并推送
  python news.py now --no-push                仅抓取预览
  python news.py now --channels wechat        仅推送到企业微信
  python news.py now --sources 36kr zhihu_hot 仅抓取指定源
  python news.py schedule                     注册每天早8点定时推送
  python news.py schedule --cron "0 8,20 * * *"  自定义 cron
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # now 子命令
    now_parser = subparsers.add_parser("now", help="立即抓取并推送")
    now_parser.add_argument('--no-push', action='store_true', help='仅抓取不推送')
    now_parser.add_argument('--channels', nargs='+', default=None,
                            choices=['email', 'wechat'], help='指定推送渠道')
    now_parser.add_argument('--sources', nargs='+', default=None,
                            help='仅抓取指定源')

    # schedule 子命令
    sched_parser = subparsers.add_parser("schedule", help="注册定时推送任务")
    sched_parser.add_argument('--cron', default="0 8 * * *",
                              help='Cron 表达式（默认: 0 8 * * *，每天早8点）')
    sched_parser.add_argument('--channels', nargs='+', default=None,
                              choices=['email', 'wechat'], help='指定推送渠道')

    args = parser.parse_args()

    if args.command == "now":
        cmd_now(args)
    elif args.command == "schedule":
        cmd_schedule(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
