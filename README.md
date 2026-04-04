# futabato.github.io

Astro + カスタム CSS で構築されたポートフォリオサイト

## コンテンツの更新方法

すべてのコンテンツは **`src/data/portfolio.json`** に集約されています。
コンポーネントやCSSを編集する必要はなく、JSONを書き換えるだけでサイトに反映されます。

### プロフィール

```jsonc
{
  "name": "futabato",
  "greeting": "Hi, there",
  "tagline": "Data Scientist",        // Hero のデコードアニメーションで表示
  "bio": "Data Scientist interested in CyberSecurity. ...",
}
```

### 所属 (affiliations)

Hero に「Lab: ○○ · Circle: ○○」のように表示されます。

```jsonc
"affiliations": [
  {
    "label": "Lab",          // 表示ラベル
    "name": "Network Security Laboratory",
    "url": "https://..."
  }
]
```

追加する場合は配列に要素を追加するだけです。

### 学歴 (education)

新しい順に並べてください。

```jsonc
"education": [
  {
    "institution": "大学名",
    "department": "学科・コース名",
    "location": "場所",
    "period": "Apr 2023 – Mar 2025",
    "note": "学位など (省略可)"       // note は任意フィールド
  }
]
```

### プロジェクト (projects)

ウィンドウ風カードとして表示されます。

```jsonc
"projects": [
  {
    "name": "プロジェクト名",        // タイトルバーに「○○.exe」として表示
    "description": "説明文",
    "blog": "https://...",           // 省略可
    "repo": "https://..."           // 省略可
  }
]
```

### 活動 (activities)

年ごとのタイムライン表示です。新しい年を先頭に追加してください。

```jsonc
"activities": [
  {
    "year": "2025",
    "items": [
      "活動内容1",
      "活動内容2"
    ]
  },
  // ... 既存の年はそのまま残す
]
```

### 資格 (certificates)

```jsonc
"certificates": [
  {
    "name": "資格名",
    "date": "取得年月 (例: Dec 2022)"
  }
]
```

### 受賞 (awards)

```jsonc
"awards": [
  {
    "name": "受賞名・大会名",
    "detail": "受賞内容の詳細"
  }
]
```

### 実績 (achievements)

```jsonc
"achievements": [
  {
    "name": "実績名",
    "date": "年 (例: 2022)"
  }
]
```

### 奨学金 (scholarship)

```jsonc
"scholarship": {
  "name": "奨学金名",
  "type": "種別 (例: Non-refundable scholarship)",
  "period": "期間 (例: Apr 2021 – Mar 2023)"
}
```

### リンク (links)

Hero (先頭4件) と Footer (全件) に表示されます。

```jsonc
"links": [
  { "label": "GitHub", "url": "https://github.com/futabato" }
]
```

## 開発

```bash
pnpm install    # 依存パッケージのインストール
pnpm dev        # 開発サーバー起動 (localhost:4321)
pnpm build      # 本番ビルド (dist/ に出力)
pnpm preview    # ビルド結果のプレビュー
```

## デプロイ

`master` ブランチに push すると GitHub Actions (`.github/workflows/deploy.yml`) が自動で GitHub Pages にデプロイします。

## AI Security Weekly Digest

AIセキュリティの日次ダイジェストを自動生成・RSS 配信しています。詳細は [scripts/README.md](scripts/README.md) を参照してください。

## License

This project is licensed under the MIT License.
