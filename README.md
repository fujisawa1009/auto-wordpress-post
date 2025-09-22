# Auto WordPress Post Generator

AI を活用した WordPress 記事自動生成・投稿システム

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?logo=docker&logoColor=white)](https://www.docker.com/)

## 🌟 特徴

- **🤖 AI記事生成**: Perplexity API を使用した約10,000字の高品質記事生成
- **📝 WordPress連携**: 下書き・公開・予約投稿の自動化
- **🔍 プレビュー機能**: 安全なHTMLプレビューで投稿前確認
- **📊 文字数制御**: 9,000-11,000字への自動調整機能
- **🔄 冪等性**: 同一入力による重複生成防止
- **⚡ 非同期処理**: Celery によるバックグラウンド処理

## 🚀 クイックスタート

### 1. 必要な準備

- [Docker](https://www.docker.com/) & [Docker Compose](https://docs.docker.com/compose/)
- [Perplexity API キー](https://www.perplexity.ai/)
- WordPress サイトとアプリケーションパスワード

### 2. インストール

```bash
# リポジトリをクローン
git clone <repository-url>
cd auto-wordpress-post

# 環境変数ファイルを作成
cp .env.example .env
```

### 3. 設定

`.env` ファイルを編集：

```bash
# Perplexity API設定
PPLX_API_KEY=your_perplexity_api_key_here

# WordPress設定
WP_BASE_URL=https://your-wordpress-site.com
WP_USERNAME=your_wp_username
WP_APPLICATION_PASSWORD=xxxx xxxx xxxx xxxx
```

**WordPress アプリケーションパスワードの取得方法：**
1. WordPress管理画面 → ユーザー → プロフィール
2. 「アプリケーションパスワード」で新規作成
3. 生成されたパスワードを `.env` に設定

### 4. 起動

```bash
# 全サービスを起動
make setup

# ブラウザでAPI仕様確認
open http://localhost:8080/docs
```

## 📝 使用方法

### 基本的な記事生成フロー

#### 1️⃣ 記事生成リクエスト

```bash
curl -X POST http://localhost:8080/api/articles/generate \
  -H "Content-Type: application/json" \
  -d '{
    "summary": "ChatGPTと生成AIの活用方法について",
    "goal": "ビジネスでの生成AI活用方法を具体的に紹介する",
    "audience": "企業の経営者・マネージャー",
    "must_topics": ["業務効率化", "コスト削減", "具体的事例"],
    "tone": "business",
    "target_chars": 10000
  }'
```

**レスポンス：**
```json
{
  "article_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Article generation started"
}
```

#### 2️⃣ 生成状況の確認

```bash
curl http://localhost:8080/api/articles/550e8400-e29b-41d4-a716-446655440000
```

#### 3️⃣ プレビュー確認

ブラウザで以下にアクセス：
```
http://localhost:8080/preview/550e8400-e29b-41d4-a716-446655440000
```

#### 4️⃣ WordPress投稿

```bash
# 即座に公開
curl -X POST http://localhost:8080/api/articles/550e8400-e29b-41d4-a716-446655440000/publish \
  -H "Content-Type: application/json" \
  -d '{"mode": "publish"}'

# 下書き保存
curl -X POST http://localhost:8080/api/articles/550e8400-e29b-41d4-a716-446655440000/publish \
  -H "Content-Type: application/json" \
  -d '{"mode": "draft"}'

# 予約投稿
curl -X POST http://localhost:8080/api/articles/550e8400-e29b-41d4-a716-446655440000/publish \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "schedule",
    "schedule_at": "2025-12-25T10:00:00"
  }'
```

### 記事生成パラメータ詳細

| パラメータ | 説明 | 必須 | 例 |
|------------|------|------|-----|
| `summary` | 記事の要約（50-1000文字） | ✅ | "AI技術の最新動向について" |
| `goal` | 記事の目的（20-500文字） | ✅ | "読者にAI活用方法を理解してもらう" |
| `audience` | 想定読者（10-200文字） | ✅ | "IT業界の技術者・マネージャー" |
| `must_topics` | 必須トピック（最大10個） | - | ["機械学習", "自動化"] |
| `bans` | 禁止事項（最大20個） | - | ["投機的内容", "未確認情報"] |
| `references` | 参考URL（最大5個） | - | ["https://example.com"] |
| `tone` | 記事のトーン | - | `tech` / `business` / `casual` / `formal` |
| `target_chars` | 目標文字数（9000-11000） | - | `10000` |
| `author` | 著者名（最大100文字） | - | "田中太郎" |

## 🛠️ 開発・運用

### 開発コマンド

```bash
# サービス管理
make up              # サービス開始
make down            # サービス停止
make logs            # ログ表示
make clean           # 完全リセット

# 開発ツール
make shell           # APIコンテナシェル
make db-shell        # データベースシェル
make migrate         # マイグレーション実行
make test            # テスト実行
make lint            # コード品質チェック
make format          # コード整形
```

### 監視・ログ

```bash
# リアルタイムログ
make logs

# 構造化ログ（JSON）
docker-compose exec api tail -f /tmp/app.json.log

# 特定サービス
docker-compose logs -f worker
docker-compose logs -f db
```

### トラブルシューティング

| 問題 | 確認方法 | 解決方法 |
|------|----------|----------|
| データベース接続エラー | `docker-compose ps db` | `docker-compose restart db` |
| ワーカーが動作しない | `docker-compose logs worker` | `docker-compose restart worker` |
| Perplexity API エラー | APIキー・クォータ確認 | `.env` 設定見直し |
| WordPress API エラー | 接続テスト実行 | 認証情報確認 |

## 📊 API 仕様

### エンドポイント一覧

| メソッド | エンドポイント | 説明 |
|----------|----------------|------|
| `POST` | `/api/articles/generate` | 記事生成開始 |
| `GET` | `/api/articles/{id}` | 記事状況取得 |
| `POST` | `/api/articles/{id}/publish` | WordPress投稿 |
| `POST` | `/api/articles/{id}/regenerate` | 記事再生成 |
| `DELETE` | `/api/articles/{id}` | 記事削除 |
| `GET` | `/api/taxonomies/sync` | カテゴリ・タグ同期 |
| `GET` | `/preview/{id}` | HTMLプレビュー |
| `GET` | `/health` | ヘルスチェック |

詳細な API 仕様は起動後に http://localhost:8080/docs で確認できます。

## 🔒 セキュリティ

- **HTTPS必須**: 全ての外部API通信
- **入力検証**: Pydantic による厳密なバリデーション
- **HTMLサニタイズ**: XSS攻撃防止
- **秘密情報管理**: 環境変数による機密情報保護
- **ログ保護**: 機密情報のログ出力除外

## 📄 ライセンス

MIT License - 詳細は [LICENSE](LICENSE) ファイルを参照

---

**Auto WordPress Post Generator** - AI-Powered Content Creation & Publishing 🚀