# GEMINI.md

## 目的
- Gemini CLI 向けのコンテキストと作業方針を定義する。

## 出力スタイル
- 言語: 日本語
- トーン: 簡潔で事実ベース
- 形式: Markdown

## 共通ルール
- 会話は日本語で行う。
- PR とコミットは Conventional Commits に従う。
- PR タイトルとコミット本文の言語: PR タイトルは Conventional Commits 形式（英語推奨）。PR 本文は日本語。コミットは Conventional Commits 形式（description は日本語）。
- 日本語と英数字の間には半角スペースを入れる。

## プロジェクト概要
Python utility that monitors multiple YouTube playlists for new videos and posts notifications to a Discord channel.

### 技術スタック
- **言語**: Python 3.6+
- **フレームワーク**: N, /, A
- **パッケージマネージャー**: pip
- **主要な依存関係**:
  - google-api-python-client>=2.29.0
  - python-dotenv>=0.19.1
  - youtube-dl>=2021.2.10
  - requests>=2.25.1

## コーディング規約
- フォーマット: 既存設定（ESLint / Prettier / formatter）に従う。
- 命名規則: 既存のコード規約に従う。
- コメント言語: 日本語
- エラーメッセージ: 英語

### 開発コマンド
```bash
# install
pip3 install -U -r requirements.txt

# dev
python3 -m src

# run
python3 -m src (from project root)

```

## 注意事項
- 認証情報やトークンはコミットしない。
- ログに機密情報を出力しない。
- 既存のプロジェクトルールがある場合はそれを優先する。

## リポジトリ固有
- **note**: YouTube playlist monitor with Discord notifications
- **configuration**: {'env_vars': ['DISCORD_TOKEN (required)', 'DISCORD_CHANNEL_ID (required)', 'GOOGLE_TOKEN (required)'], 'config_file': 'playlists.json (playlist IDs)'}
- **execution**: Must run from project root to read .env
**api_integrations:**
  - YouTube Data API
  - Discord Bot API
- **disclaimer**: Developer not responsible for misuse