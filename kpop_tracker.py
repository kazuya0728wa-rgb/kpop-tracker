"""K-pop最新情報ダイジェスト — GitHub Actions版

対象: IVE / LE SSERAFIM / TWICE / NewJeans / Hearts2Hearts
収集: チケット・イベント・カムバック・TV出演（日本限定）
通知: 2日に1回 Discord Embed（チケット情報は特別強調）

情報収集パイプライン:
  1. DuckDuckGo site:x.com 検索（公式JPアカウント）
  2. 公式サイトスクレイピング
  3. チケットサイト（イープラス・ローチケ）
  4. Google News RSS

差分検出（SHA256）で既出除外 → DeepSeek API で重要度判定・要約 → Discord送信
"""

import hashlib
import json
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from openai import OpenAI
from duckduckgo_search import DDGS

from config import (
    GROUPS, TICKET_SITES,
    TICKET_KEYWORDS, EVENT_KEYWORDS, COMEBACK_KEYWORDS, TV_KEYWORDS,
    TOP_N, MAX_CANDIDATES_PER_GROUP, HISTORY_RETENTION_DAYS,
    TWO_DAYS_AGO_HOURS, DDG_SLEEP_SEC,
)

# ── 環境変数 ──────────────────────────────────────────────────────────────────
WEBHOOK      = os.environ["DISCORD_WEBHOOK"]
BOT_TOKEN    = os.environ.get("DISCORD_BOT_TOKEN", "")
CHANNEL_ID   = os.environ.get("DISCORD_CHANNEL_ID", "")
DEEPSEEK_KEY = os.environ["DEEPSEEK_API_KEY"]

DATA_DIR      = os.path.join(os.path.dirname(__file__), "data")
HISTORY_FILE  = os.path.join(DATA_DIR, "history.json")
JST           = timezone(timedelta(hours=9))
CUTOFF_TIME   = datetime.now(timezone.utc) - timedelta(hours=TWO_DAYS_AGO_HOURS)

WEB_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en;q=0.9",
}
DISCORD_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent":   "DiscordBot (https://example.com, 1.0)",
}


# ── ユーティリティ ─────────────────────────────────────────────────────────────
def _fetch_html(url: str, timeout: int = 15) -> str:
    """URLからHTMLを取得。"""
    req = urllib.request.Request(url, headers=WEB_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _make_hash(title: str, url: str = "") -> str:
    """ニュースの一意ハッシュ。"""
    normalized = re.sub(r"[^\w\s]", "", title.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    domain = ""
    try:
        domain = urlparse(url).netloc
    except Exception:
        pass
    return hashlib.sha256((normalized + domain).encode("utf-8")).hexdigest()[:12]


# ── 1. X(Twitter) 検索 ────────────────────────────────────────────────────────
def search_x_for_group(group: dict) -> list[dict]:
    """グループごとに3クエリでX検索。"""
    name = group["name"]
    x_acc = group["x_account"]
    name_jp = group["name_jp"]
    queries = [
        f'site:x.com {x_acc} チケット OR ライブ OR コンサート OR ツアー OR 発売',
        f'site:x.com "{name}" Japan OR 日本 チケット OR 先行 OR 抽選 OR 一般発売',
        f'site:x.com "{name}" アルバム OR 新曲 OR カムバック OR リリース OR Mステ',
    ]
    items = []
    for q in queries:
        try:
            results = DDGS().text(q, max_results=6)
            for r in (results or []):
                items.append({
                    "title":    r.get("title", "").strip(),
                    "url":      r.get("href", "").strip(),
                    "body":     r.get("body", "").strip(),
                    "source":   "X (Twitter)",
                    "group_id": group["id"],
                    "priority": 1,
                })
        except Exception as e:
            print(f"  [DDG SKIP] {q[:50]}... → {e}")
        time.sleep(DDG_SLEEP_SEC)
    return items


# ── 2. 公式サイトスクレイピング ────────────────────────────────────────────────
def scrape_official_sites(group: dict) -> list[dict]:
    """公式サイトからニュース・スケジュールを取得。"""
    items = []
    for site in group["official_sites"]:
        parser = site["parser"]
        url = site["url"]
        try:
            if parser == "weverse":
                items.extend(_parse_weverse(url, group))
            elif parser == "ive_php":
                items.extend(_parse_ive_php(url, group))
            elif parser == "generic_html":
                items.extend(_parse_generic_html(url, group))
        except Exception as e:
            print(f"  [SITE SKIP] {group['name']} {url[:50]} → {e}")
    return items


def _parse_weverse(url: str, group: dict) -> list[dict]:
    """LE SSERAFIM / NewJeans (Weverse系) のニュース・スケジュールページ。"""
    html = _fetch_html(url)
    soup = BeautifulSoup(html, "lxml")
    items = []
    # <a> タグからリンクとタイトルを抽出
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        text = a.get_text(strip=True)
        if not text or len(text) < 5:
            continue
        # /posts/news/xxx or /posts/schedule/xxx のパターン
        if "/posts/" in href:
            full_url = urllib.parse.urljoin(url, href)
            items.append({
                "title":    text[:120],
                "url":      full_url,
                "body":     "",
                "source":   group["name"] + " 公式",
                "group_id": group["id"],
                "priority": 2,
            })
    return items[:15]


def _parse_ive_php(url: str, group: dict) -> list[dict]:
    """IVE 公式サイト (PHP動的)。"""
    html = _fetch_html(url)
    soup = BeautifulSoup(html, "lxml")
    items = []
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        text = a.get_text(strip=True)
        if not text or len(text) < 5:
            continue
        if "newsShw" in href or "news" in href.lower():
            full_url = urllib.parse.urljoin(url, href)
            items.append({
                "title":    text[:120],
                "url":      full_url,
                "body":     "",
                "source":   "IVE 公式",
                "group_id": group["id"],
                "priority": 2,
            })
    return items[:15]


def _parse_generic_html(url: str, group: dict) -> list[dict]:
    """汎用HTMLパーサー (TWICE, H2H Universal Music等)。"""
    html = _fetch_html(url)
    soup = BeautifulSoup(html, "lxml")
    items = []
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        text = a.get_text(strip=True)
        if not text or len(text) < 8:
            continue
        # ナビゲーションリンクを除外
        if href in ("#", "/", "") or text in ("TOP", "HOME", "MENU"):
            continue
        full_url = href if href.startswith("http") else urllib.parse.urljoin(url, href)
        items.append({
            "title":    text[:120],
            "url":      full_url,
            "body":     "",
            "source":   group["name"] + " 公式",
            "group_id": group["id"],
            "priority": 2,
        })
    return items[:15]


# ── 3. チケットサイトスクレイピング ────────────────────────────────────────────
def scrape_ticket_sites(group: dict) -> list[dict]:
    """イープラス・ローチケからチケット情報を収集。"""
    items = []
    for ts in group.get("ticket_sites", []):
        if not ts.get("active", True):
            continue
        site_id = ts["site"]
        site_def = TICKET_SITES.get(site_id)
        if not site_def:
            continue
        url = site_def["url_template"].format(artist_id=ts["artist_id"])
        try:
            if site_id == "eplus":
                items.extend(_scrape_eplus(url, group, site_def["name"]))
            elif site_id == "lawson":
                items.extend(_scrape_lawson(url, group, site_def["name"]))
        except Exception as e:
            print(f"  [TICKET SKIP] {group['name']} {site_def['name']} → {e}")
    return items


def _scrape_eplus(url: str, group: dict, site_name: str) -> list[dict]:
    """イープラスのアーティストページからイベント情報を取得。"""
    html = _fetch_html(url)
    soup = BeautifulSoup(html, "lxml")
    items = []
    # イベントリスト要素を探す
    for el in soup.select("a[href*='/sf/detail/']"):
        text = el.get_text(strip=True)
        href = el.get("href", "")
        if not text or len(text) < 5:
            continue
        full_url = urllib.parse.urljoin("https://eplus.jp", href)
        items.append({
            "title":    f"[{site_name}] {text[:100]}",
            "url":      full_url,
            "body":     "",
            "source":   site_name,
            "group_id": group["id"],
            "priority": 1,  # チケット情報は最優先
        })
    return items[:10]


def _scrape_lawson(url: str, group: dict, site_name: str) -> list[dict]:
    """ローチケのアーティストページからイベント情報を取得。"""
    html = _fetch_html(url)
    soup = BeautifulSoup(html, "lxml")
    items = []
    for el in soup.select("a[href*='/concert/'], a[href*='/order/']"):
        text = el.get_text(strip=True)
        href = el.get("href", "")
        if not text or len(text) < 5:
            continue
        full_url = href if href.startswith("http") else urllib.parse.urljoin("https://l-tike.com", href)
        items.append({
            "title":    f"[{site_name}] {text[:100]}",
            "url":      full_url,
            "body":     "",
            "source":   site_name,
            "group_id": group["id"],
            "priority": 1,
        })
    return items[:10]


# ── 4. Google News RSS ─────────────────────────────────────────────────────────
def fetch_google_news(group: dict) -> list[dict]:
    """Google News RSSでグループの日本語ニュースを取得。"""
    query = urllib.parse.quote(group["google_news_query"])
    rss_url = (
        f"https://news.google.com/rss/search?q={query}"
        f"&hl=ja&gl=JP&ceid=JP:ja"
    )
    try:
        req = urllib.request.Request(rss_url, headers=WEB_HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
        root = ET.fromstring(raw)
    except Exception as e:
        print(f"  [RSS SKIP] {group['name']} → {e}")
        return []

    items = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link  = (item.findtext("link")  or "").strip()
        pub   = item.findtext("pubDate") or ""
        try:
            pub_dt = parsedate_to_datetime(pub).astimezone(timezone.utc)
        except Exception:
            pub_dt = datetime.now(timezone.utc)
        if title and pub_dt >= CUTOFF_TIME:
            items.append({
                "title":    title,
                "url":      link,
                "body":     (item.findtext("description") or "")[:200],
                "source":   "Google News",
                "group_id": group["id"],
                "priority": 3,
            })
    return items


# ── 差分検出 ──────────────────────────────────────────────────────────────────
def load_history() -> dict:
    if not os.path.exists(HISTORY_FILE):
        return {"last_run": None, "items": {}}
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"last_run": None, "items": {}}


def save_history(history: dict) -> None:
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def filter_new_items(items: list[dict], history: dict) -> list[dict]:
    now = datetime.now(JST).isoformat()
    new_items = []
    for item in items:
        h = _make_hash(item.get("title", ""), item.get("url", ""))
        if h in history["items"]:
            history["items"][h]["last_seen"] = now
        else:
            history["items"][h] = {
                "title": item.get("title", ""),
                "first_seen": now,
                "last_seen": now,
            }
            new_items.append(item)
    history["last_run"] = now
    return new_items


def cleanup_history(history: dict) -> int:
    cutoff = (datetime.now(JST) - timedelta(days=HISTORY_RETENTION_DAYS)).isoformat()
    to_remove = [h for h, item in history["items"].items()
                 if item.get("last_seen", "") < cutoff]
    for h in to_remove:
        del history["items"][h]
    return len(to_remove)


def deduplicate(items: list[dict]) -> list[dict]:
    seen, result = set(), []
    for item in items:
        key = re.sub(r"[^\w]", "", item["title"].lower())[:40]
        if key and key not in seen:
            seen.add(key)
            result.append(item)
    return result


# ── DeepSeek API で重要度判定・要約 ───────────────────────────────────────────
def curate_with_deepseek(items: list[dict], now: datetime) -> list[dict]:
    """候補リストから重要な情報のみを厳選・日本語要約。"""

    # グループ名リストを生成
    group_names = ", ".join(
        f"{g['name']}({g['name_jp']})" for g in GROUPS if g["active"]
    )

    # 候補テキスト
    candidates = ""
    for i, item in enumerate(items[:100], 1):
        body = f"\n   概要: {item['body'][:150]}" if item.get("body") else ""
        candidates += (
            f"{i}. [{item['source']}] [{item.get('group_id', '?')}] {item['title']}\n"
            f"   URL: {item['url']}{body}\n\n"
        )

    prompt = f"""あなたはK-popの日本活動情報に特化したキュレーターです。
今日は {now.strftime('%Y年%m月%d日')} です。
対象グループ: {group_names}

以下はK-popグループの日本活動に関する候補リストです。

{candidates}

この中から **日本のファンにとって重要な情報のみ** を選び、以下のJSON形式で回答してください。
コードブロック・説明文は不要です。JSONだけ出力してください。

[
  {{
    "rank": 1,
    "group_id": "グループID（ive/le_sserafim/twice/newjeans/h2h）",
    "category": "カテゴリ（ticket/event/comeback/tv）",
    "headline": "見出し（日本語・35文字以内）",
    "summary": "要約（日本語・2〜3文・60〜100文字）",
    "detail": "詳細（日本語・5〜8文・200〜400文字。日時・会場・購入方法などを含む）",
    "url": "元記事URL",
    "source": "情報源名"
  }}
]

■ 重要度判定（この優先度で選定）:
1. 【最重要・必ず含める】チケット情報（先行販売・一般発売・抽選開始・販売日告知）
2. 【重要】ライブ/ツアー日程の新規発表、カムバック・新曲リリース（日本盤）、ファンミーティング
3. 【中】日本のTV出演（Mステ・CDTV・FNS・THE FIRST TAKE等）
4. 【除外】雑誌掲載のみ、SNS更新のみ、グッズ情報のみ、韓国国内のみの情報

■ ルール:
- 重要度が「除外」に該当する情報は返さないでください
- 同じ内容の重複は1件にまとめる
- 最大{TOP_N}件まで
- 該当する重要情報がなければ空配列 [] を返す
- category は必ず ticket / event / comeback / tv のいずれか"""

    client = OpenAI(api_key=DEEPSEEK_KEY, base_url="https://api.deepseek.com")
    resp = client.chat.completions.create(
        model="deepseek-chat",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.choices[0].message.content.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise


# ── Discord 送信 ───────────────────────────────────────────────────────────────
def _get_group_by_id(group_id: str) -> dict | None:
    for g in GROUPS:
        if g["id"] == group_id:
            return g
    return None


def build_embeds(top_items: list[dict], now: datetime, total_collected: int) -> list[dict]:
    """グループ別カラーEmbedを構築。チケット情報は特別強調。"""
    next_run = (now + timedelta(days=2)).strftime("%Y-%m-%d 09:00 JST")
    numbers = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧"]

    # チケット情報を先頭に並べ替え
    ticket_items = [i for i in top_items if i.get("category") == "ticket"]
    other_items = [i for i in top_items if i.get("category") != "ticket"]
    sorted_items = ticket_items + other_items

    fields = []
    for idx, item in enumerate(sorted_items):
        group = _get_group_by_id(item.get("group_id", ""))
        emoji = group["emoji"] if group else "🎵"
        group_name = group["name"] if group else "?"
        cat = item.get("category", "")
        n = numbers[idx] if idx < len(numbers) else f"({idx+1})"

        # チケット情報は特別強調
        if cat == "ticket":
            name = f"🔥🎫 {emoji} {group_name} — {item['headline']}"
        elif cat == "tv":
            name = f"📺 {emoji} {group_name} — {item['headline']}"
        elif cat == "comeback":
            name = f"🎶 {emoji} {group_name} — {item['headline']}"
        else:
            name = f"{n} {emoji} {group_name} — {item['headline']}"

        source = item.get("source", "")
        fields.append({
            "name":   name,
            "value":  f"{item['summary']}\n*出典: {source}*",
            "inline": False,
        })

    # メインのEmbed色: チケット情報があればゴールド、なければホットピンク
    color = 0xFFD700 if ticket_items else 0xFF69B4

    embed = {
        "title":       "🎵 K-pop 最新情報ダイジェスト",
        "description": (
            f"{now.strftime('%Y-%m-%d')}  ·  厳選 **{len(sorted_items)}件** / "
            f"収集 {total_collected}件中"
        ),
        "color":       color,
        "fields":      fields,
        "footer":      {"text": f"次回: {next_run}"},
        "timestamp":   now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    return [embed]


def build_buttons(top_items: list[dict]) -> list[dict]:
    """「詳しく」ボタンを構築。"""
    ticket_items = [i for i in top_items if i.get("category") == "ticket"]
    other_items = [i for i in top_items if i.get("category") != "ticket"]
    sorted_items = ticket_items + other_items

    buttons = []
    for idx, item in enumerate(sorted_items[:5]):
        group = _get_group_by_id(item.get("group_id", ""))
        emoji = group["emoji"] if group else "🎵"
        buttons.append({
            "type":      2,
            "style":     1 if item.get("category") != "ticket" else 3,  # 3=Success(green) for tickets
            "label":     f"{emoji} 詳しく",
            "custom_id": f"kpop_detail_{item.get('group_id', 'unknown')}_{idx}",
        })
    return buttons


def send_via_bot(payload: dict) -> None:
    url  = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages"
    hdrs = {
        "Authorization":  f"Bot {BOT_TOKEN}",
        "Content-Type":   "application/json",
        "User-Agent":     "DiscordBot (https://example.com, 1.0)",
    }
    data = json.dumps(payload, ensure_ascii=False).encode()
    req  = urllib.request.Request(url, data=data, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f"Discord Bot API: {r.status}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        print(f"Discord Bot ERROR {e.code}: {body}")
        if e.code == 400 and "components" in payload:
            print("ボタン除去して再送...")
            payload.pop("components", None)
            send_via_bot(payload)


def send_via_webhook(payload: dict) -> None:
    payload.pop("components", None)
    data = json.dumps(payload, ensure_ascii=False).encode()
    req  = urllib.request.Request(WEBHOOK, data=data, headers=DISCORD_HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        print(f"Discord Webhook: {r.status}")


def send_discord(payload: dict) -> None:
    if BOT_TOKEN and CHANNEL_ID:
        send_via_bot(payload)
    else:
        print("BOT_TOKEN/CHANNEL_ID 未設定 → Webhookで送信")
        send_via_webhook(payload)


def save_details(top_items: list[dict]) -> None:
    """詳細データを data/latest.json に保存（Worker参照）。"""
    os.makedirs(DATA_DIR, exist_ok=True)

    # グループ別にネスト
    groups_data = {}
    ticket_first = [i for i in top_items if i.get("category") == "ticket"]
    others = [i for i in top_items if i.get("category") != "ticket"]
    sorted_items = ticket_first + others

    for idx, item in enumerate(sorted_items):
        gid = item.get("group_id", "unknown")
        if gid not in groups_data:
            groups_data[gid] = []
        groups_data[gid].append(item)

    out = {
        "generated_at": datetime.now(JST).isoformat(),
        "items": sorted_items,
        "groups": groups_data,
    }
    path = os.path.join(DATA_DIR, "latest.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"詳細データ保存: {path}")


# ── メイン ─────────────────────────────────────────────────────────────────────
def main():
    now      = datetime.now(JST)
    print(f"収集開始: {now.strftime('%Y-%m-%d %H:%M JST')}")

    active_groups = [g for g in GROUPS if g.get("active", False)]
    print(f"対象グループ: {', '.join(g['name'] for g in active_groups)}")

    all_items: list[dict] = []

    for group in active_groups:
        print(f"\n── {group['emoji']} {group['name']} ──")

        # 1. X検索
        x_items = search_x_for_group(group)
        print(f"  X検索: {len(x_items)}件")
        all_items.extend(x_items)

        # 2. 公式サイト
        site_items = scrape_official_sites(group)
        print(f"  公式サイト: {len(site_items)}件")
        all_items.extend(site_items)

        # 3. チケットサイト
        ticket_items = scrape_ticket_sites(group)
        print(f"  チケットサイト: {len(ticket_items)}件")
        all_items.extend(ticket_items)

        # 4. Google News RSS
        news_items = fetch_google_news(group)
        print(f"  Google News: {len(news_items)}件")
        all_items.extend(news_items)

    all_items = deduplicate(all_items)
    print(f"\n重複排除後: {len(all_items)}件")

    # 差分検出
    history = load_history()
    new_items = filter_new_items(all_items, history)
    removed = cleanup_history(history)
    save_history(history)
    print(f"差分検出: {len(new_items)}件が新規 / {len(all_items) - len(new_items)}件が既出 / {removed}件を履歴削除")

    if not new_items:
        print("新規ニュースなし → 送信スキップ")
        return

    # グループ毎に候補数を制限
    limited = []
    counts = {}
    for item in new_items:
        gid = item.get("group_id", "?")
        counts[gid] = counts.get(gid, 0) + 1
        if counts[gid] <= MAX_CANDIDATES_PER_GROUP:
            limited.append(item)

    print(f"→ DeepSeek APIで重要度判定中（候補{len(limited)}件）...")
    top_items = curate_with_deepseek(limited, now)
    print(f"厳選完了: {len(top_items)}件")

    if not top_items:
        print("重要な情報なし → 送信スキップ")
        return

    # 詳細データ保存
    save_details(top_items)

    # Discord Embed構築・送信
    embeds = build_embeds(top_items, now, len(all_items))
    buttons = build_buttons(top_items)

    payload = {
        "embeds": embeds,
        "components": [{"type": 1, "components": buttons}] if buttons else [],
    }

    send_discord(payload)
    print("完了")


if __name__ == "__main__":
    main()
