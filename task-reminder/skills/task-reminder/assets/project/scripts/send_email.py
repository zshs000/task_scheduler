"""
邮件发送脚本
用于发送定时提醒邮件
"""
import argparse
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from datetime import datetime


def load_config():
    """加载邮件配置（优先从 skill 根目录读取）"""
    candidates = []
    for parent in Path(__file__).resolve().parents:
        candidates.append(parent / "config" / "email_config.json")

    for path in candidates:
        if path.is_file():
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)

    raise FileNotFoundError("config/email_config.json")


def send_reminder(content, subject=None):
    """
    发送提醒邮件

    Args:
        content: 邮件内容
        subject: 邮件主题（可选）
    """
    try:
        config = load_config()

        # 创建邮件
        msg = MIMEMultipart()
        msg['From'] = config['smtp_user']
        msg['To'] = config['recipient']
        msg['Subject'] = subject or '贴心提醒'

        # 邮件正文
        body = f"""
{content}

---
发送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
来自: 你的提醒小助手
"""
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        # 发送邮件
        with smtplib.SMTP(config['smtp_host'], config['smtp_port']) as server:
            server.starttls()
            server.login(config['smtp_user'], config['smtp_password'])
            server.send_message(msg)

        print(f"[OK] 邮件发送成功: {content}")
        return True

    except FileNotFoundError:
        print("[ERROR] 找不到配置文件 config/email_config.json")
        print("请先配置邮件信息")
        return False
    except smtplib.SMTPAuthenticationError:
        print("[ERROR] SMTP认证失败，请检查邮箱和密码")
        return False
    except Exception as e:
        print(f"[ERROR] 发送邮件失败: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='发送提醒邮件')
    parser.add_argument('--content', required=True, help='提醒内容')
    parser.add_argument('--subject', default='贴心提醒', help='邮件主题')

    args = parser.parse_args()

    success = send_reminder(args.content, args.subject)
    exit(0 if success else 1)
