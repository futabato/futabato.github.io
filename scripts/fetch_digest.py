#!/usr/bin/env python3
"""
AI Security Weekly Digest
- RSSフィードから記事を自動収集
- AIセキュリティ関連記事をフィルタリング
- Anthropic Claude APIで日本語要約を生成
- Atom/RSSフィードとして出力
"""

import hashlib
import html as html_mod
import ipaddress
import json
import logging
import os
import re
import socket
import time
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, tostring

import feedparser
import httpx
import yaml

# ── ロギング設定 ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ── 定数 ──
SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT = SCRIPTS_DIR.parent  # futabato.github.io repo root
CONFIG_PATH = SCRIPTS_DIR / "digest_config.yaml"
OUTPUT_DIR = ROOT / "public" / "rss"
FEED_OUTPUT = OUTPUT_DIR / "feed.xml"
INDEX_OUTPUT = OUTPUT_DIR / "index.html"
ARCHIVE_DIR = SCRIPTS_DIR / "archive"
MANUAL_PICKS_PATH = ROOT / "manual_picks.yaml"
ISSUE_PICKS_DIR = ROOT / ".issue_picks"
JST = timezone(timedelta(hours=9))


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


# ── フィード収集 ──
def fetch_all_feeds(config: dict, days_back: int = 7) -> list[dict]:
    """全ソースからRSSエントリを取得し、直近N日分をフィルタ"""
    cutoff = datetime.now(UTC) - timedelta(days=days_back)
    articles = []

    for source in config["feeds"]:
        log.info(f"Fetching: {source['name']}")
        try:
            feed = feedparser.parse(source["url"])
            for entry in feed.entries:
                # 日付解析
                published = None
                for date_field in ("published_parsed", "updated_parsed"):
                    t = getattr(entry, date_field, None)
                    if t:
                        published = datetime(*t[:6], tzinfo=UTC)
                        break
                if published and published < cutoff:
                    continue

                articles.append(
                    {
                        "title": entry.get("title", ""),
                        "link": entry.get("link", ""),
                        "summary": entry.get("summary", "")[:1000],
                        "published": published or datetime.now(UTC),
                        "source_name": source["name"],
                        "category": source["category"],
                    }
                )
        except Exception as e:
            log.warning(f"Failed to fetch {source['name']}: {e}")

    log.info(f"Total articles fetched: {len(articles)}")
    return articles


# ── フィルタリング ──
def matches_keywords(text: str, config: dict) -> bool:
    """AIセキュリティ関連かどうかをキーワードで判定"""
    text_lower = text.lower()
    kw = config["keywords"]

    # primary キーワード: いずれか1つで採用
    for term in kw["primary"]:
        if term.lower() in text_lower:
            return True

    # compound: AI系 + セキュリティ系の両方を含む
    has_ai = any(t.lower() in text_lower for t in kw["compound"]["ai_terms"])
    has_sec = any(t.lower() in text_lower for t in kw["compound"]["security_terms"])
    if has_ai and has_sec:
        return True

    return False


def filter_articles(articles: list[dict], config: dict) -> list[dict]:
    """AIセキュリティ関連の記事のみ抽出"""
    filtered = []
    seen_links = set()
    for a in articles:
        if a["link"] in seen_links:
            continue
        text = f"{a['title']} {a['summary']}"
        if matches_keywords(text, config):
            filtered.append(a)
            seen_links.add(a["link"])

    # 日付の新しい順にソート
    filtered.sort(key=lambda x: x["published"], reverse=True)

    max_items = config["output"].get("max_items_per_digest", 20)
    filtered = filtered[:max_items]
    log.info(f"Filtered articles: {len(filtered)}")
    return filtered


# ── URL安全性チェック ──
def is_safe_url(url: str) -> bool:
    """SSRF対策: 内部IPアドレスへのアクセスをブロック"""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        # DNS解決してIPアドレスを検証
        for info in socket.getaddrinfo(hostname, None):
            addr = ipaddress.ip_address(info[4][0])
            if addr.is_private or addr.is_loopback or addr.is_link_local:
                log.warning(f"Blocked private/internal URL: {url}")
                return False
    except Exception:
        return False
    return True


# ── 手動キュレーション ──
def load_manual_picks() -> list[dict]:
    """manual_picks.yaml から未処理のURLを読み込み"""
    if not MANUAL_PICKS_PATH.exists():
        return []

    with open(MANUAL_PICKS_PATH) as f:
        data = yaml.safe_load(f) or {}

    picks = data.get("picks") or []
    # consumed でないものだけ
    return [p for p in picks if isinstance(p, dict) and not p.get("consumed")]


def fetch_manual_articles(picks: list[dict]) -> list[dict]:
    """手動ピックのURLからタイトル・本文を取得"""
    if not picks:
        return []

    articles = []
    with httpx.Client(timeout=30.0, follow_redirects=True, headers={"User-Agent": "AI-Security-Digest/1.0"}) as client:
        for pick in picks:
            url = pick.get("url", "").strip()
            if not url:
                continue

            if not is_safe_url(url):
                log.warning(f"Skipping unsafe URL: {url}")
                continue

            log.info(f"Fetching manual pick: {url}")
            try:
                resp = client.get(url)
                resp.raise_for_status()
                page_html = resp.text

                # 簡易タイトル抽出
                title = pick.get("note") or ""
                title_match = re.search(r"<title[^>]*>([^<]+)</title>", page_html, re.IGNORECASE)
                if title_match:
                    page_title = title_match.group(1).strip()
                    if not title:
                        title = page_title
                    else:
                        title = f"{page_title} — {title}"

                # 簡易本文抽出（meta description + 先頭テキスト）
                summary = ""
                desc_match = re.search(
                    r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]+content=["\']([^"\']+)',
                    page_html,
                    re.IGNORECASE,
                )
                if desc_match:
                    summary = desc_match.group(1).strip()

                if not title:
                    title = url

                # ソース名を推定
                domain = urlparse(url).netloc.replace("www.", "")
                source_map = {
                    "x.com": "X (Twitter)",
                    "twitter.com": "X (Twitter)",
                    "arxiv.org": "arXiv",
                    "github.com": "GitHub",
                }
                source_name = source_map.get(domain, domain)

                articles.append(
                    {
                        "title": title,
                        "link": url,
                        "summary": summary[:1000] or pick.get("note", ""),
                        "published": datetime.now(UTC),
                        "source_name": f"📌 {source_name}",
                        "category": "curated",
                        "tags": pick.get("tags", ["curated"]),
                        "is_manual_pick": True,
                    }
                )

            except Exception as e:
                log.warning(f"Failed to fetch manual pick {url}: {e}")
                # フェッチ失敗でもnoteがあれば記事として追加
                if pick.get("note"):
                    articles.append(
                        {
                            "title": pick["note"],
                            "link": url,
                            "summary": pick.get("note", ""),
                            "published": datetime.now(UTC),
                            "source_name": "📌 Manual Pick",
                            "category": "curated",
                            "tags": pick.get("tags", ["curated"]),
                            "is_manual_pick": True,
                        }
                    )

    log.info(f"Manual picks loaded: {len(articles)}")
    return articles


def mark_picks_consumed():
    """処理済みのピックに consumed: true を付与"""
    if not MANUAL_PICKS_PATH.exists():
        return

    with open(MANUAL_PICKS_PATH) as f:
        data = yaml.safe_load(f) or {}

    picks = data.get("picks") or []
    changed = False
    for pick in picks:
        if isinstance(pick, dict) and pick.get("url") and not pick.get("consumed"):
            pick["consumed"] = True
            pick["consumed_at"] = datetime.now(JST).strftime("%Y-%m-%d")
            changed = True

    if changed:
        data["picks"] = picks
        with open(MANUAL_PICKS_PATH, "w") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
        log.info("Manual picks marked as consumed")


# ── GitHub Issue連携 ──
def load_issue_picks() -> list[dict]:
    """GitHub Actions経由でIssueから抽出されたURLを読み込み
    .issue_picks/ ディレクトリにJSONファイルとして配置される想定
    """
    if not ISSUE_PICKS_DIR.exists():
        return []

    picks = []
    for f in ISSUE_PICKS_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            if isinstance(data, list):
                picks.extend(data)
            elif isinstance(data, dict):
                picks.append(data)
        except Exception as e:
            log.warning(f"Failed to load issue pick {f}: {e}")

    return picks


# ── LLM要約 ──
def summarize_with_claude(articles: list[dict], config: dict) -> list[dict]:
    """Anthropic Claude APIで記事を日本語要約"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.warning("ANTHROPIC_API_KEY not set. Skipping summarization.")
        for a in articles:
            a["ai_summary"] = a["summary"][:200]
            a["tags"] = [a["category"]]
        return articles

    model = config["anthropic"]["model"]

    with httpx.Client(
        base_url="https://api.anthropic.com",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        timeout=60.0,
    ) as client:
        # バッチで要約（API呼び出し回数を抑制）
        batch_size = 5
        for i in range(0, len(articles), batch_size):
            batch = articles[i : i + batch_size]
            entries_text = "\n\n".join(
                f"[{j + 1}] Title: {a['title']}\nSource: {a['source_name']}\n"
                f"URL: {a['link']}\nExcerpt: {a['summary'][:300]}"
                for j, a in enumerate(batch)
            )

            prompt = f"""以下の{len(batch)}件のAIセキュリティ関連記事について、それぞれ日本語で要約してください。

{entries_text}

以下のJSON形式で返してください。JSON以外のテキストは含めないでください。
[
  {{
    "index": 1,
    "summary_ja": "2-3文の日本語要約",
    "tags": ["タグ1", "タグ2"]
  }},
  ...
]

タグは以下から選択: research, vulnerability, policy, tool, incident, governance,
evaluation, agent-security, model-safety, adversarial, regulation"""

            try:
                resp = client.post(
                    "/v1/messages",
                    json={
                        "model": model,
                        "max_tokens": 2000,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                text = "".join(block.get("text", "") for block in data.get("content", []))

                # JSONパース
                text = re.sub(r"```json|```", "", text).strip()
                summaries = json.loads(text)

                for item in summaries:
                    idx = item["index"] - 1
                    if 0 <= idx < len(batch):
                        batch[idx]["ai_summary"] = item["summary_ja"]
                        batch[idx]["tags"] = item.get("tags", [batch[idx]["category"]])

            except Exception as e:
                log.warning(f"Summarization failed for batch {i}: {e}")
                for a in batch:
                    a.setdefault("ai_summary", a["summary"][:200])
                    a.setdefault("tags", [a["category"]])

            # レート制限対策
            if i + batch_size < len(articles):
                time.sleep(2)

    return articles


# ── Atomフィード生成 ──
def generate_atom_feed(articles: list[dict], config: dict) -> str:
    """Atom 1.0フィードXMLを生成"""
    ATOM_NS = "http://www.w3.org/2005/Atom"
    out = config["output"]
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    feed = Element("feed", xmlns=ATOM_NS)

    SubElement(feed, "title").text = out["feed_title"]
    SubElement(feed, "subtitle").text = out["feed_description"]
    SubElement(feed, "id").text = out.get("site_url", "urn:ai-security-digest")
    SubElement(feed, "updated").text = now

    link_self = SubElement(feed, "link")
    link_self.set("rel", "self")
    link_self.set("href", out.get("feed_url", ""))

    link_alt = SubElement(feed, "link")
    link_alt.set("rel", "alternate")
    link_alt.set("href", out.get("site_url", ""))

    author = SubElement(feed, "author")
    SubElement(author, "name").text = "AI Security Digest Bot"

    for article in articles:
        entry = SubElement(feed, "entry")

        SubElement(entry, "title").text = article["title"]

        link = SubElement(entry, "link")
        link.set("href", article["link"])
        link.set("rel", "alternate")

        # 一意なID
        uid = hashlib.sha256(article["link"].encode()).hexdigest()[:16]
        SubElement(entry, "id").text = f"urn:ai-security-digest:{uid}"

        pub = article["published"].strftime("%Y-%m-%dT%H:%M:%SZ")
        SubElement(entry, "published").text = pub
        SubElement(entry, "updated").text = pub

        # 要約をコンテンツとして（XSS対策でエスケープ）
        esc = html_mod.escape
        summary_text = esc(article.get("ai_summary", article["summary"][:200]))
        content = SubElement(entry, "content")
        content.set("type", "html")
        tags_html = "".join(f'<span class="tag">{esc(t)}</span> ' for t in article.get("tags", []))
        content.text = (
            f"<p>{summary_text}</p><p><strong>Source:</strong> {esc(article['source_name'])}</p><p>{tags_html}</p>"
        )

        # カテゴリタグ
        for tag in article.get("tags", []):
            cat = SubElement(entry, "category")
            cat.set("term", tag)

        source_el = SubElement(entry, "source")
        SubElement(source_el, "title").text = article["source_name"]

    # 整形
    raw_xml = tostring(feed, encoding="unicode", xml_declaration=False)
    declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
    try:
        pretty = minidom.parseString(raw_xml).toprettyxml(indent="  ")
        # minidomの宣言を除去して自前で付与
        pretty = "\n".join(pretty.split("\n")[1:])
        return declaration + pretty
    except Exception:
        return declaration + raw_xml


# ── HTMLインデックスページ生成 ──
def generate_index_html(articles: list[dict], config: dict) -> str:
    """GitHub Pages用のHTMLインデックス"""
    out = config["output"]
    week = datetime.now(JST).strftime("%Y年%m月%d日週")

    esc = html_mod.escape
    rows = ""
    for a in articles:
        tags = " ".join(f'<span class="tag">{esc(t)}</span>' for t in a.get("tags", []))
        summary = esc(a.get("ai_summary", a["summary"][:150]))
        date_str = a["published"].strftime("%m/%d")
        curated_class = " curated" if a.get("is_manual_pick") else ""
        rows += f"""
        <article class="entry{curated_class}">
          <div class="meta">
            <time>{date_str}</time>
            <span class="source">{esc(a["source_name"])}</span>
          </div>
          <h3><a href="{esc(a["link"], quote=True)}" target="_blank" rel="noopener">{esc(a["title"])}</a></h3>
          <p>{summary}</p>
          <div class="tags">{tags}</div>
        </article>"""

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{out["feed_title"]} | futabato</title>
  <link rel="alternate" type="application/atom+xml" title="Atom Feed" href="feed.xml">
  <meta name="description" content="AIセキュリティに関する週次ニュースダイジェスト">
  <style>
    :root {{ --bg: #0d1117; --fg: #e6edf3; --muted: #8b949e; --accent: #58a6ff; --green: #3fb950; --card: #161b22; --border: #30363d; --tag-bg: #1f2937; }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--fg); max-width: 800px; margin: 0 auto; padding: 2rem 1rem; }}
    nav {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem; padding-bottom: 1rem; border-bottom: 1px solid var(--border); }}
    nav a {{ color: var(--muted); text-decoration: none; font-size: 0.85rem; }}
    nav a:hover {{ color: var(--fg); }}
    .nav-home {{ font-family: 'Courier New', monospace; color: var(--green); font-weight: bold; }}
    header {{ margin-bottom: 2rem; }}
    header h1 {{ font-size: 1.5rem; margin-bottom: 0.5rem; font-family: 'Courier New', monospace; }}
    header p {{ color: var(--muted); font-size: 0.9rem; margin-bottom: 0.5rem; }}
    .header-links {{ display: flex; gap: 1rem; }}
    .feed-link {{ color: var(--accent); text-decoration: none; font-size: 0.85rem; }}
    .feed-link:hover {{ text-decoration: underline; }}
    .entry {{ background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 1.25rem; margin-bottom: 1rem; }}
    .entry.curated {{ border-left: 3px solid var(--green); }}
    .entry .meta {{ display: flex; gap: 1rem; color: var(--muted); font-size: 0.8rem; margin-bottom: 0.5rem; }}
    .entry h3 {{ font-size: 1rem; margin-bottom: 0.5rem; }}
    .entry h3 a {{ color: var(--accent); text-decoration: none; }}
    .entry h3 a:hover {{ text-decoration: underline; }}
    .entry p {{ color: var(--muted); font-size: 0.9rem; line-height: 1.5; }}
    .tags {{ margin-top: 0.5rem; display: flex; flex-wrap: wrap; gap: 0.4rem; }}
    .tag {{ background: var(--tag-bg); color: var(--accent); padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.75rem; }}
    footer {{ margin-top: 2rem; padding-top: 1rem; border-top: 1px solid var(--border); color: var(--muted); font-size: 0.8rem; text-align: center; }}
    footer a {{ color: var(--muted); }}
  </style>
</head>
<body>
  <nav>
    <a href="/" class="nav-home">&lt; futabato.exe</a>
    <div class="header-links">
      <a class="feed-link" href="feed.xml">Atom Feed</a>
      <a href="https://github.com/futabato/futabato.github.io" target="_blank">Source</a>
    </div>
  </nav>
  <header>
    <h1>{out["feed_title"]}</h1>
    <p>{week} | {len(articles)}件の記事（自動収集 + 手動キュレーション）</p>
  </header>
  <main>{rows}
  </main>
  <footer>
    <a href="/">futabato.github.io</a> | Auto-generated weekly
  </footer>
</body>
</html>"""


# ── メイン ──
def main():
    config = load_config()

    log.info("=== AI Security Weekly Digest ===")

    # 1. RSS自動収集
    articles = fetch_all_feeds(config, days_back=7)

    # 2. フィルタリング（自動収集分のみ）
    articles = filter_articles(articles, config)

    # 3. 手動キュレーション（フィルタ不要、そのまま追加）
    manual_picks = load_manual_picks()
    issue_picks = load_issue_picks()
    all_picks = manual_picks + issue_picks
    manual_articles = fetch_manual_articles(all_picks)

    # 手動ピックを先頭に配置（📌マーク付き）
    articles = manual_articles + articles

    if not articles:
        log.info("No articles found this week. Skipping digest generation.")
        return

    # 4. LLM要約
    articles = summarize_with_claude(articles, config)

    # 5. 出力
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    # Atomフィード
    atom_xml = generate_atom_feed(articles, config)
    FEED_OUTPUT.write_text(atom_xml, encoding="utf-8")
    log.info(f"Atom feed written: {FEED_OUTPUT}")

    # HTMLインデックス
    html = generate_index_html(articles, config)
    INDEX_OUTPUT.write_text(html, encoding="utf-8")
    log.info(f"Index HTML written: {INDEX_OUTPUT}")

    # アーカイブ（週ごと）
    week_label = datetime.now(JST).strftime("%Y-W%V")
    archive_path = ARCHIVE_DIR / f"digest-{week_label}.json"
    archive_data = [
        {
            "title": a["title"],
            "link": a["link"],
            "source": a["source_name"],
            "published": a["published"].isoformat(),
            "summary_ja": a.get("ai_summary", ""),
            "tags": a.get("tags", []),
        }
        for a in articles
    ]
    archive_path.write_text(json.dumps(archive_data, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info(f"Archive written: {archive_path}")

    # 手動ピックを処理済みに
    mark_picks_consumed()

    # Issue picks クリーンアップ
    if ISSUE_PICKS_DIR.exists():
        for f in ISSUE_PICKS_DIR.glob("*.json"):
            f.unlink()
        log.info("Issue picks cleaned up")

    log.info("Done.")


if __name__ == "__main__":
    main()
