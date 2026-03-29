"""K-pop Tracker — グループ定義・情報源・全設定

グループの追加・削除・設定変更はこのファイルだけで完結する。
"""

# ── 対象グループ ──────────────────────────────────────────────────────────────
GROUPS = [
    {
        "id": "ive",
        "name": "IVE",
        "name_jp": "アイブ",
        "active": True,
        "color": 0x9B59B6,       # 紫
        "emoji": "💜",
        "x_account": "@IVEstarship_JP",
        "official_sites": [
            {
                "type": "news",
                "url": "http://ive-official.jp/mob/news/newsLis.php?site=DIVE&ima=1943",
                "parser": "ive_php",
            },
        ],
        "ticket_sites": [
            {"site": "eplus",  "artist_id": "0000151800", "active": True},
            {"site": "lawson", "artist_id": "000000000885455", "active": True},
            {"site": "pia",    "artist_id": "LB090017", "active": False},
        ],
        "google_news_query": "IVE アイブ Japan ライブ チケット カムバ",
    },
    {
        "id": "le_sserafim",
        "name": "LE SSERAFIM",
        "name_jp": "ル・セラフィム",
        "active": True,
        "color": 0xE74C3C,       # 赤
        "emoji": "🔴",
        "x_account": "@le_sserafim_jp",
        "official_sites": [
            {"type": "news",     "url": "https://www.le-sserafim.jp/posts/news",                       "parser": "weverse"},
            {"type": "schedule", "url": "https://www.le-sserafim.jp/posts/schedule?category=LIVE",     "parser": "weverse"},
            {"type": "schedule", "url": "https://www.le-sserafim.jp/posts/schedule?category=EVENT",    "parser": "weverse"},
        ],
        "ticket_sites": [
            {"site": "eplus",  "artist_id": "0000153223", "active": True},
            {"site": "lawson", "artist_id": "000000000898939", "active": True},
            {"site": "pia",    "artist_id": "M6200023", "active": False},
        ],
        "google_news_query": "LE SSERAFIM ル・セラフィム Japan ライブ チケット カムバ",
    },
    {
        "id": "twice",
        "name": "TWICE",
        "name_jp": "トゥワイス",
        "active": True,
        "color": 0xF39C12,       # オレンジ
        "emoji": "🟠",
        "x_account": "@JYPETWICE_JAPAN",
        "official_sites": [
            {"type": "news",     "url": "https://www.twicejapan.com/news",     "parser": "generic_html"},
            {"type": "schedule", "url": "https://www.twicejapan.com/schedule", "parser": "generic_html"},
        ],
        "ticket_sites": [
            {"site": "eplus",  "artist_id": "0000082150", "active": True},
            {"site": "lawson", "artist_id": "000000000410126", "active": True},
            {"site": "pia",    "artist_id": "3B140191", "active": False},
        ],
        "google_news_query": "TWICE トゥワイス Japan ライブ チケット カムバ",
    },
    {
        "id": "newjeans",
        "name": "NewJeans",
        "name_jp": "ニュージーンズ",
        "active": True,
        "color": 0x3498DB,       # 青
        "emoji": "🔵",
        "x_account": "@NewJeans_jp",
        "official_sites": [
            {"type": "news",     "url": "https://www.newjeans.jp/posts/news",                       "parser": "weverse"},
            {"type": "schedule", "url": "https://www.newjeans.jp/posts/schedule?category=LIVE",     "parser": "weverse"},
            {"type": "schedule", "url": "https://www.newjeans.jp/posts/schedule?category=EVENT",    "parser": "weverse"},
        ],
        "ticket_sites": [
            {"site": "eplus",  "artist_id": "0000154593", "active": True},
            {"site": "lawson", "artist_id": "000000000908078", "active": True},
            {"site": "pia",    "artist_id": "M8250010", "active": False},
        ],
        "google_news_query": "NewJeans ニュージーンズ Japan ライブ チケット カムバ",
    },
    {
        "id": "h2h",
        "name": "Hearts2Hearts",
        "name_jp": "ハーツトゥーハーツ",
        "active": True,
        "color": 0x2ECC71,       # 緑
        "emoji": "💚",
        "x_account": "@Hearts2HeartsJP",
        "official_sites": [
            {
                "type": "news",
                "url": "https://www.universal-music.co.jp/hearts2hearts/",
                "parser": "generic_html",
            },
        ],
        "ticket_sites": [
            {"site": "eplus",  "artist_id": "0000169453", "active": True},
            {"site": "pia",    "artist_id": "P2250007", "active": False},
        ],
        "google_news_query": "Hearts2Hearts ハーツトゥーハーツ Japan ライブ チケット カムバ",
    },
]

# ── チケットサイト定義 ────────────────────────────────────────────────────────
TICKET_SITES = {
    "eplus": {
        "name": "イープラス",
        "url_template": "https://eplus.jp/sf/word/{artist_id}",
    },
    "lawson": {
        "name": "ローチケ",
        "url_template": "https://l-tike.com/artist/{artist_id}/",
    },
    "pia": {
        "name": "チケットぴあ",
        "url_template": "https://t.pia.jp/pia/artist/artists.do?artistsCd={artist_id}",
    },
}

# ── 重要度判定キーワード ──────────────────────────────────────────────────────
TICKET_KEYWORDS = [
    "チケット", "先行", "一般発売", "抽選", "FC先行", "受付",
    "ticket", "presale", "general sale",
]
EVENT_KEYWORDS = [
    "ライブ", "コンサート", "ツアー", "ファンミーティング", "公演",
    "LIVE", "TOUR", "FANMEETING", "ARENA", "DOME",
]
COMEBACK_KEYWORDS = [
    "新曲", "アルバム", "シングル", "MV", "Music Video",
    "リリース", "発売", "初回限定", "comeback", "release",
]
TV_KEYWORDS = [
    "Mステ", "MUSIC STATION", "CDTV", "ミュージックステーション",
    "FNS", "THE FIRST TAKE", "テレビ出演", "TV出演",
    "NHK", "テレ朝", "TBS", "フジテレビ", "日テレ",
]

# ── 実行設定 ──────────────────────────────────────────────────────────────────
TOP_N = 8                       # 最大通知件数（全グループ合計）
MAX_CANDIDATES_PER_GROUP = 20   # DeepSeek API に渡す候補の上限/グループ
HISTORY_RETENTION_DAYS = 30
TWO_DAYS_AGO_HOURS = 48         # 収集範囲（過去48時間）
DDG_SLEEP_SEC = 2               # DuckDuckGo レート制限対策
