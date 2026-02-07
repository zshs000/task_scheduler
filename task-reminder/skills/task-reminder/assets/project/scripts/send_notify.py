"""
统一通知分发脚本
支持同时通过邮件和企业微信发送通知
"""
import argparse
import json
import sys
from pathlib import Path


def load_notify_config():
    """加载通知渠道配置"""
    candidates = []
    for parent in Path(__file__).resolve().parents:
        candidates.append(parent / "config" / "notify_config.json")

    for path in candidates:
        if path.is_file():
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)

    return {"channels": ["email"]}


def send_notify(content, subject=None, title=None, channels=None):
    """
    统一通知分发

    Args:
        content: 通知内容
        subject: 邮件主题（可选）
        title: 微信消息标题（可选）
        channels: 渠道列表（可选，默认从配置读取）

    Returns:
        bool: 至少一个渠道成功则返回 True
    """
    if channels is None:
        config = load_notify_config()
        channels = config.get("channels", ["email"])

    results = {}

    if "email" in channels:
        try:
            from send_email import send_reminder
            results["email"] = send_reminder(content, subject)
        except ImportError:
            # 尝试从同目录导入
            try:
                scripts_dir = str(Path(__file__).resolve().parent)
                if scripts_dir not in sys.path:
                    sys.path.insert(0, scripts_dir)
                from send_email import send_reminder
                results["email"] = send_reminder(content, subject)
            except Exception as e:
                print(f"[WARN] 邮件渠道不可用: {e}")
                results["email"] = False
        except Exception as e:
            print(f"[WARN] 邮件发送失败: {e}")
            results["email"] = False

    if "wechat" in channels:
        try:
            from send_wechat import send_wechat
            results["wechat"] = send_wechat(content, title)
        except ImportError:
            try:
                scripts_dir = str(Path(__file__).resolve().parent)
                if scripts_dir not in sys.path:
                    sys.path.insert(0, scripts_dir)
                from send_wechat import send_wechat
                results["wechat"] = send_wechat(content, title)
            except Exception as e:
                print(f"[WARN] 企业微信渠道不可用: {e}")
                results["wechat"] = False
        except Exception as e:
            print(f"[WARN] 企业微信发送失败: {e}")
            results["wechat"] = False

    success_count = sum(1 for v in results.values() if v)
    total_count = len(results)

    if success_count == 0 and total_count > 0:
        print(f"[ERROR] 所有通知渠道均失败")
        return False

    if success_count < total_count:
        print(f"[WARN] 部分渠道发送成功 ({success_count}/{total_count})")

    return success_count > 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='统一通知分发')
    parser.add_argument('--content', required=True, help='通知内容')
    parser.add_argument('--subject', default='贴心提醒', help='邮件主题')
    parser.add_argument('--title', default=None, help='微信消息标题')
    parser.add_argument('--channels', nargs='+', default=None,
                        choices=['email', 'wechat'], help='指定通知渠道')

    args = parser.parse_args()

    success = send_notify(args.content, args.subject, args.title, args.channels)
    exit(0 if success else 1)
