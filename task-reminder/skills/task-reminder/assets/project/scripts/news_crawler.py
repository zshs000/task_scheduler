"""
新闻爬虫 + 推送脚本
支持多源抓取、去重、格式化、推送
"""
import argparse
import hashlib
import json
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

import requests

try:
    import feedparser
except ImportError:
    feedparser = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None


# ---------------------------------------------------------------------------
# 配置加载
# ---------------------------------------------------------------------------

def _find_config(name):
    for parent in Path(__file__).resolve().parents:
        p = parent / "config" / name
        if p.is_file():
            return p
    return None


def load_news_config():
    p = _find_config("news_config.json")
    if p:
        with open(p, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "sources": [],
        "custom_rss": [],
        "max_items_per_source": 10,
        "max_total_items": 30,
    }


# ---------------------------------------------------------------------------
# 去重数据库
# ---------------------------------------------------------------------------

def _db_path():
    for parent in Path(__file__).resolve().parents:
        data_dir = parent / "data"
        if data_dir.is_dir():
            return data_dir / "news_dedup.db"
    data_dir = Path(__file__).resolve().parent.parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "news_dedup.db"


def _init_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS seen_news (
            md5 TEXT PRIMARY KEY,
            title TEXT,
            source TEXT,
            created_at TEXT
        )
    """)
    conn.commit()


def _cleanup_old(conn, days=7):
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    conn.execute("DELETE FROM seen_news WHERE created_at < ?", (cutoff,))
    conn.commit()


def _is_seen(conn, title):
    md5 = hashlib.md5(title.encode('utf-8')).hexdigest()
    row = conn.execute("SELECT 1 FROM seen_news WHERE md5 = ?", (md5,)).fetchone()
    return row is not None


def _mark_seen(conn, title, source):
    md5 = hashlib.md5(title.encode('utf-8')).hexdigest()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO seen_news (md5, title, source, created_at) VALUES (?, ?, ?, ?)",
            (md5, title, source, datetime.now().isoformat())
        )
        conn.commit()
    except sqlite3.Error:
        pass


# ---------------------------------------------------------------------------
# 内置爬虫（JSON API）
# ---------------------------------------------------------------------------

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def fetch_36kr(limit=10):
    """36氪热榜"""
    items = []
    try:
        url = "https://gateway.36kr.com/api/mis/nav/home/nav/rank/hot"
        payload = {"partner_id": "wap", "param": {"siteId": 1, "platformId": 2}}
        resp = requests.post(url, json=payload, headers=HEADERS, timeout=10)
        data = resp.json()
        hot_list = data.get("data", ).get("hotRankList", [])
        for item in hot_list[:limit]:
            template = item.get("templateMaterial", {})
            title = template.get("widgetTitle", "").strip()
            item_id = template.get("itemId", "")
            if title:
                items.append({
                    "title": title,
                    "url": f"https://36kr.com/p/{item_id}" if item_id else "",
                    "source": "36氪",
                })
    except Exception as e:
        print(f"[WARN] 36氪抓取失败: {e}")
    return items


def fetch_zhihu_hot(limit=10):
    """知乎热榜"""
    items = []
    try:
        url = "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=50"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        data = resp.json()
        for entry in data.get("data", [])[:limit]:
            target = entry.get("target", {})
            title = target.get("title", "").strip()
            qid = target.get("id", "")
            if title:
                items.append({
                    "title": title,
                    "url": f"https://www.zhihu.com/question/{qid}" if qid else "",
                    "source": "知乎热榜",
                })
    except Exception as e:
        print(f"[WARN] 知乎热榜抓取失败: {e}")
    return items


def fetch_sina_news(limit=10):
    """新浪新闻滚动"""
    items = []
    try:
        url = "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2509&k=&num=50&page=1"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        data = resp.json()
        for entry in data.get("result", {}).get("data", [])[:limit]:
            title = entry.get("title", "").strip()
            link = entry.get("url", "")
            if title:
                items.append({
                    "title": title,
                    "url": link,
                    "source": "新浪新闻",
                })
    except Exception as e:
        print(f"[WARN] 新浪新闻抓取失败: {e}")
    return items


def fetch_infoq(limit=10):
    """InfoQ 中文站"""
    items = []
    try:
        url = "https://www.infoq.cn/public/v1/article/getList"
        payload = {"type": 1, "size": limit}
        resp = requests.post(url, json=payload, headers={
            **HEADERS,
            "Content-Type": "application/json",
            "Referer": "https://www.infoq.cn/"
        }, timeout=10)
        data = resp.json()
        for entry in data.get("data", [])[:limit]:
            title = entry.get("article_title", "").strip()
            uuid = entry.get("uuid", "")
            if title:
                items.append({
                    "title": title,
                    "url": f"https://www.infoq.cn/article/{uuid}" if uuid else "",
                    "source": "InfoQ",
                })
    except Exception as e:
        print(f"[WARN] InfoQ 抓取失败: {e}")
    return items


BUILTIN_FETCHERS = {
    "36kr": fetch_36kr,
    "zhihu_hot": fetch_zhihu_hot,
    "sina_news": fetch_sina_news,
    "infoq": fetch_infoq,
}


# ---------------------------------------------------------------------------
# RSS 抓取
# ---------------------------------------------------------------------------

def fetch_rss(name, url, limit=10):
    """通过 feedparser 解析 RSS 源"""
    if feedparser is None:
        print(f"[WARN] feedparser 未安装，跳过 RSS 源: {name}")
        return []
    items = []
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:limit]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "")
            if title:
                items.append({
                    "title": title,
                    "url": link,
                    "source": name,
                })
    except Exception as e:
        print(f"[WARN] RSS 源 {name} 抓取失败: {e}")
    return items


# ---------------------------------------------------------------------------
# 抓取入口
# ---------------------------------------------------------------------------

def crawl_news(sources_filter=None):
    """
    抓取新闻

    Args:
        sources_filter: 仅抓取指定源（列表），None 表示全部

    Returns:
        list[dict]: 去重后的新闻列表
    """
    config = load_news_config()
    max_per = config.get("max_items_per_source", 10)
    max_total = config.get("max_total_items", 30)

    db = sqlite3.connect(str(_db_path()))
    _init_db(db)
    _cleanup_old(db)

    all_items = []

    # 内置源
    for src in config.get("sources", []):
        name = src.get("name", "")
        if not src.get("enabled", True):
            continue
        if sources_filter and name not in sources_filter:
            continue
        fetcher = BUILTIN_FETCHERS.get(name)
        if fetcher:
            print(f"[INFO] 正在抓取: {name}")
            items = fetcher(limit=max_per)
            new_items = []
            for item in items:
                if not _is_seen(db, item["title"]):
                    _mark_seen(db, item["title"], item["source"])
                    new_items.append(item)
            all_items.extend(new_items)
            print(f"  获取 {len(items)} 条，新增 {len(new_items)} 条")

    # 自定义 RSS
    for rss in config.get("custom_rss", []):
        name = rss.get("name", "")
        rss_url = rss.get("url", "")
        if not rss.get("enabled", True) or not rss_url:
            continue
        if sources_filter and name not in sources_filter:
            continue
        print(f"[INFO] 正在抓取 RSS: {name}")
        items = fetch_rss(name, rss_url, limit=max_per)
        new_items = []
        for item in items:
            if not _is_seen(db, item["title"]):
                _mark_seen(db, item["title"], item["source"])
                new_items.append(item)
        all_items.extend(new_items)
        print(f"  获取 {len(items)} 条，新增 {len(new_items)} 条")

    db.close()

    # 截断到最大条数
    if len(all_items) > max_total:
        all_items = all_items[:max_total]

    return all_items


# ---------------------------------------------------------------------------
# 格式化
# ---------------------------------------------------------------------------

def format_digest_plain(items):
    """纯文本格式（邮件用）"""
    if not items:
        return "暂无新的新闻资讯。"

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"新闻早报 - {now_str}", "=" * 40, ""]

    grouped = {}
    for item in items:
        src = item.get("source", "未知")
        grouped.setdefault(src, []).append(item)

    for src, src_items in grouped.items():
        lines.append(f"【{src}】")
        for i, item in enumerate(src_items, 1):
            title = item["title"]
            url = item.get("url", "")
            if url:
                lines.append(f"  {i}. {title}")
                lines.append(f"     {url}")
            else:
                lines.append(f"  {i}. {title}")
        lines.append("")

    lines.append(f"共 {len(items)} 条新资讯")
    return "\n".join(lines)


def format_digest_markdown(items):
    """Markdown 格式（企业微信用）"""
    if not items:
        return "暂无新的新闻资讯。"

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"## 新闻早报 - {now_str}", ""]

    grouped = {}
    for item in items:
        src = item.get("source", "未知")
        grouped.setdefault(src, []).append(item)

    for src, src_items in grouped.items():
        lines.append(f"### {src}")
        for i, item in enumerate(src_items, 1):
            title = item["title"]
            url = item.get("url", "")
            if url:
                lines.append(f"> {i}. [{title}]({url})")
            else:
                lines.append(f"> {i}. {title}")
        lines.append("")

    lines.append(f"共 **{len(items)}** 条新资讯")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 推送
# ---------------------------------------------------------------------------

def push_news(items, channels=None):
    """
    推送新闻摘要

    Args:
        items: 新闻列表
        channels: 渠道列表
    """
    scripts_dir = str(Path(__file__).resolve().parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    try:
        from send_notify import send_notify
    except ImportError as e:
        print(f"[ERROR] 无法导入 send_notify: {e}")
        return False

    plain = format_digest_plain(items)
    md = format_digest_markdown(items)

    # 根据渠道选择格式
    if channels and channels == ["wechat"]:
        content = md
    elif channels and channels == ["email"]:
        content = plain
    else:
        content = plain

    now_str = datetime.now().strftime("%Y-%m-%d")
    return send_notify(
        content=content,
        subject=f"新闻早报 - {now_str}",
        title=f"新闻早报 - {now_str}",
        channels=channels,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='新闻爬虫 + 推送')
    parser.add_argument('--no-push', action='store_true', help='仅抓取不推送（调试）')
    parser.add_argument('--channels', nargs='+', default=None,
                        choices=['email', 'wechat'], help='指定推送渠道')
    parser.add_argument('--sources', nargs='+', default=None,
                        help='仅抓取指定源（如: 36kr zhihu_hot）')

    args = parser.parse_args()

    print("[INFO] 开始抓取新闻...")
    items = crawl_news(sources_filter=args.sources)

    if not items:
        print("[INFO] 没有新的新闻")
        sys.exit(0)

    print(f"\n[INFO] 共获取 {len(items)} 条新闻")

    if args.no_push:
        print("\n--- 预览 (纯文本) ---")
        print(format_digest_plain(items))
        print("\n--- 预览 (Markdown) ---")
        print(format_digest_markdown(items))
    else:
        print("[INFO] 正在推送...")
        success = push_news(items, channels=args.channels)
        sys.exit(0 if success else 1)
