# Music Tracker (K-pop / J-pop)

K-pop・J-popアーティストの日本活動情報を2日に1回自動収集し、Discordに通知するツール。

## チャンネル

| チャンネル | 対象アーティスト | Discord通知先 |
|---|---|---|
| kpop | IVE / LE SSERAFIM / TWICE / NewJeans / Hearts2Hearts | `DISCORD_WEBHOOK` |
| jpop | Mrs. GREEN APPLE / timelesz / Mr.Children / Snow Man | `DISCORD_WEBHOOK_JPOP` |

## 仕組み

```
GitHub Actions (2日に1回 09:04 JST)
    │
    ▼
kpop_tracker.py --channel kpop|jpop
    ├─ DuckDuckGo site:x.com 検索
    ├─ 公式サイトスクレイピング
    ├─ チケットサイト（イープラス・ローチケ）
    └─ Google News RSS
         │
         ▼
    重複排除 → 差分検出（SHA256）
         │
         ▼
    DeepSeek API で重要度判定・要約（最大8件）
         │
         ▼
    Discord Embed送信（チケット情報は特別強調 🔥🎫）
```

## ファイル構成

| ファイル | 役割 |
|---|---|
| `config.py` | グループ定義・チャンネル定義・全設定 |
| `kpop_tracker.py` | メインスクリプト（`--channel` で切替） |
| `.github/workflows/kpop-digest.yml` | GitHub Actions（kpop → jpop の順に実行） |
| `worker/` | Cloudflare Worker（「詳しく」ボタン応答） |
| `data/` | 履歴・最新データ（チャンネル別） |

## GitHub Secrets

| Secret | 用途 |
|---|---|
| `DISCORD_WEBHOOK` | K-pop チャンネル Webhook |
| `DISCORD_WEBHOOK_JPOP` | J-pop チャンネル Webhook |
| `DISCORD_BOT_TOKEN` | Bot API（省略可） |
| `DISCORD_CHANNEL_ID` | K-pop Bot送信先（省略可） |
| `DISCORD_CHANNEL_ID_JPOP` | J-pop Bot送信先（省略可） |
| `DEEPSEEK_API_KEY` | DeepSeek API |

## アーティスト追加

`config.py` の `KPOP_GROUPS` または `JPOP_GROUPS` にエントリを追加するだけ。

## 手動実行

GitHub Actions → 「音楽最新情報ダイジェスト」→ Run workflow
