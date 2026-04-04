# AI Security Daily Digest

AIセキュリティに関する日次ニュースダイジェストを自動生成し、Atom フィードとして配信しています。

- **Atom フィード**: https://futabato.github.io/rss/feed.xml
- **Web ページ**: https://futabato.github.io/rss/

## 仕組み

毎日 9:00 JST に GitHub Actions が自動実行されます。

```
RSS フィード (20+ ソース)
  │
  ▼
キーワードフィルタリング ── AIセキュリティ関連の記事を抽出
  │
  ├── 手動ピック (manual_picks.yaml / GitHub Issue)
  │
  ▼
Claude API で日本語要約・タグ付け
  │
  ▼
Atom フィード + HTML ページを生成 → GitHub Pages で配信
```

## フィードソース

| カテゴリ | ソース例 |
|---------|---------|
| 研究 | arXiv cs.CR / cs.AI / cs.CL |
| セキュリティニュース | The Hacker News, Bleeping Computer, Krebs on Security |
| AI/ML 専門 | Simon Willison's Weblog, AI Snake Oil |
| ベンダー | Google Security Blog, Microsoft Security Blog |
| 日本語 | piyolog, Security NEXT, 徳丸浩の日記, セキュリティのアレ, サイバーセキュリティ.com |
| 政策 | JPCERT/CC, IPA, デジタル庁, 総務省, NIST, CISA |

全ソースは [`digest_config.yaml`](digest_config.yaml) を参照。

## 手動キュレーション

自動収集に加え、気になった記事を手動で追加する方法が 2 つあります。

### GitHub Issue (モバイル対応)

[Issue テンプレート](../../issues/new?template=pick.yml) から URL を投稿するだけ。`pick` ラベルが付き、次回のダイジェスト実行時に自動で取り込まれます。Issue は処理後に自動クローズされます。

> **Note**: 手動ピックも自動収集と同様にキーワードフィルタリングと上限 (5件/日) の対象です。AIセキュリティに関連しない記事や、上限を超えた分はダイジェストに含まれません。

### manual_picks.yaml

```yaml
picks:
  - url: "https://example.com/article"
    note: "一言メモ"
    tags: ["agent-security", "evaluation"]
```

push すれば次回実行時に処理され、`consumed: true` に更新されます。

## ファイル構成

```
scripts/
  fetch_digest.py       # ダイジェスト生成スクリプト
  digest_config.yaml    # フィードソース・キーワード・出力設定
  archive/              # 日次アーカイブ (JSON)
manual_picks.yaml       # 手動キュレーション
public/rss/
  feed.xml              # Atom フィード (自動生成)
  index.html            # Web ページ (自動生成)
.github/
  workflows/
    daily-digest.yml    # 日次実行ワークフロー
    process-picks.yml   # Issue → picks 抽出
  ISSUE_TEMPLATE/
    pick.yml            # 手動ピック用テンプレート
pyproject.toml          # Python 依存管理 (uv) + ruff 設定
```
