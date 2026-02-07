"""
企业微信 Webhook 机器人发送脚本
用于通过企业微信群机器人推送消息
"""
import argparse
import json
import requests
from pathlib import Path


def load_config():
    """加载企业微信配置（优先从 skill 根目录读取）"""
    candidates = []
    for parent in Path(__file__).resolve().parents:
        candidates.append(parent / "config" / "wechat_config.json")

    for path in candidates:
        if path.is_file():
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)

    raise FileNotFoundError("config/wechat_config.json")


def send_wechat(content, title=None, msg_type="text"):
    """
    发送企业微信消息

    Args:
        content: 消息内容
        title: 消息标题（仅 markdown 类型有效）
        msg_type: 消息类型 text|markdown
    """
    try:
        config = load_config()
        webhook_url = config.get("webhook_url", "")
        mentioned_list = config.get("mentioned_list", [])

        if not webhook_url or "YOUR_KEY" in webhook_url:
            print("[ERROR] 请先配置企业微信 Webhook URL")
            print("编辑 config/wechat_config.json，填入真实的 webhook key")
            return False

        if msg_type == "markdown":
            body = f"### {title}\n\n{content}" if title else content
            payload = {
                "msgtype": "markdown",
                "markdown": {"content": body}
            }
        else:
            payload = {
                "msgtype": "text",
                "text": {
                    "content": f"{title}\n\n{content}" if title else content,
                    "mentioned_list": mentioned_list
                }
            }

        resp = requests.post(webhook_url, json=payload, timeout=10)
        result = resp.json()

        if result.get("errcode") == 0:
            print(f"[OK] 企业微信发送成功")
            return True
        else:
            print(f"[ERROR] 企业微信发送失败: {result.get('errmsg', '未知错误')}")
            return False

    except FileNotFoundError:
        print("[ERROR] 找不到配置文件 config/wechat_config.json")
        print("请先配置企业微信 Webhook 信息")
        return False
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] 请求失败: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] 发送企业微信消息失败: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='发送企业微信消息')
    parser.add_argument('--content', required=True, help='消息内容')
    parser.add_argument('--title', default=None, help='消息标题')
    parser.add_argument('--type', dest='msg_type', default='text',
                        choices=['text', 'markdown'], help='消息类型')

    args = parser.parse_args()

    success = send_wechat(args.content, args.title, args.msg_type)
    exit(0 if success else 1)
