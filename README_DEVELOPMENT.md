# Auto WordPress Post Generator

AI-powered WordPress article generator and publisher using Perplexity API.

## Features

- **AI Article Generation**: Generate ~10,000 character articles using Perplexity API
- **WordPress Integration**: Automatic publishing with draft/publish/schedule modes
- **Preview System**: Safe HTML preview before publishing
- **Character Control**: Automatic adjustment to target 9,000-11,000 characters
- **Idempotency**: Prevent duplicate generation with same input
- **Async Processing**: Non-blocking article generation with Celery workers

## 🚀 起動手順

### 1. 前提条件

- **Docker & Docker Compose** がインストール済み
- **Perplexity API キー** (https://www.perplexity.ai/)
- **WordPress サイト** とアプリケーションパスワード

### 2. プロジェクトセットアップ

```bash
# プロジェクトディレクトリに移動
cd auto-wordpress-post

# 環境変数ファイルをコピー
cp .env.example .env
```

### 3. 環境変数設定

`.env` ファイルを編集して以下を設定：

```bash
# Perplexity API
PPLX_API_KEY=your_perplexity_api_key_here

# WordPress設定
WP_BASE_URL=https://your-wordpress-site.com
WP_USERNAME=your_wp_username
WP_APPLICATION_PASSWORD=xxxx xxxx xxxx xxxx

# その他の設定はデフォルトのまま
```

### 4. WordPress アプリケーションパスワード取得

1. WordPress管理画面にログイン
2. **ユーザー** → **プロフィール** へ移動
3. **アプリケーションパスワード** セクションで新しいパスワードを作成
4. 生成されたパスワードを `.env` の `WP_APPLICATION_PASSWORD` に設定

### 5. サービス起動

```bash
# 全てのサービスを起動（推奨）
make setup

# または手動で起動
docker-compose build
docker-compose up -d
make migrate
```

### 6. 動作確認

- **API ドキュメント**: http://localhost:8080/docs
- **ヘルスチェック**: http://localhost:8080/health
- **タクソノミー同期**: http://localhost:8080/api/taxonomies/sync

## 📝 使用方法

### 記事生成から投稿まで

#### 1. 記事生成開始
```bash
curl -X POST http://localhost:8080/api/articles/generate \
  -H "Content-Type: application/json" \
  -d '{
    "summary": "AIと機械学習の最新動向について詳しく解説",
    "goal": "読者にAI技術の現状と将来性を理解してもらう",
    "audience": "IT業界従事者、エンジニア",
    "must_topics": ["機械学習", "ディープラーニング", "自然言語処理"],
    "tone": "tech",
    "target_chars": 10000
  }'
```

レスポンス例：
```json
{
  "article_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "pending",
  "message": "Article generation started"
}
```

#### 2. 生成状況確認
```bash
curl http://localhost:8080/api/articles/123e4567-e89b-12d3-a456-426614174000
```

#### 3. プレビュー表示
ブラウザで以下にアクセス：
```
http://localhost:8080/preview/123e4567-e89b-12d3-a456-426614174000
```

#### 4. WordPress投稿
```bash
# 即座に公開
curl -X POST http://localhost:8080/api/articles/123e4567-e89b-12d3-a456-426614174000/publish \
  -H "Content-Type: application/json" \
  -d '{"mode": "publish"}'

# 下書きとして保存
curl -X POST http://localhost:8080/api/articles/123e4567-e89b-12d3-a456-426614174000/publish \
  -H "Content-Type: application/json" \
  -d '{"mode": "draft"}'

# 予約投稿
curl -X POST http://localhost:8080/api/articles/123e4567-e89b-12d3-a456-426614174000/publish \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "schedule",
    "schedule_at": "2025-12-25T10:00:00"
  }'
```

## 🛠️ 開発・運用コマンド

```bash
# サービス管理
make up            # サービス開始
make down          # サービス停止
make logs          # ログ表示
make clean         # 完全クリーンアップ

# 開発ツール
make shell         # APIコンテナのシェル
make db-shell      # PostgreSQLシェル
make migrate       # データベースマイグレーション
make test          # テスト実行

# コード品質
make lint          # コードチェック
make format        # コード整形

# デバッグ
make logs          # 全サービスのログ
docker-compose logs api      # APIサービスのみ
docker-compose logs worker   # ワーカーのみ
```

## 🔧 トラブルシューティング

### よくある問題と解決方法

#### 1. データベース接続エラー
```bash
# データベースコンテナの状況確認
docker-compose ps db

# データベースログ確認
docker-compose logs db

# データベース再起動
docker-compose restart db
```

#### 2. Perplexity API エラー
- API キーが正しく設定されているか確認
- API クォータが残っているか確認
- ネットワーク接続を確認

#### 3. WordPress API エラー
```bash
# WordPress接続テスト
curl -u username:app_password https://your-site.com/wp-json/wp/v2/
```

#### 4. ワーカーが動作しない
```bash
# ワーカーの状況確認
docker-compose logs worker

# Redis接続確認
docker-compose exec redis redis-cli ping

# ワーカー再起動
docker-compose restart worker
```

#### 5. 文字数が目標に達しない
- `target_chars` パラメータを調整
- `must_topics` を追加して内容を充実
- プロンプトの調整が必要な場合は設定変更

## 📋 設定オプション

### 記事生成パラメータ

| パラメータ | 説明 | デフォルト | 範囲 |
|------------|------|------------|------|
| `summary` | 記事の要約 | 必須 | 50-1000文字 |
| `goal` | 記事の目的 | 必須 | 20-500文字 |
| `audience` | 想定読者 | 必須 | 10-200文字 |
| `must_topics` | 必須トピック | `[]` | 最大10個 |
| `bans` | 禁止事項 | `[]` | 最大20個 |
| `references` | 参考URL | `[]` | 最大5個 |
| `tone` | 記事のトーン | `tech` | tech/business/casual/formal |
| `target_chars` | 目標文字数 | `10000` | 9000-11000 |
| `author` | 著者名 | `null` | 最大100文字 |

### 環境変数

| 変数名 | 説明 | 必須 | デフォルト |
|--------|------|------|------------|
| `PPLX_API_KEY` | Perplexity APIキー | ✅ | - |
| `WP_BASE_URL` | WordPress URL | ✅ | - |
| `WP_USERNAME` | WordPressユーザー名 | ✅ | - |
| `WP_APPLICATION_PASSWORD` | アプリケーションパスワード | ✅ | - |
| `DATABASE_URL` | PostgreSQL接続URL | - | 自動設定 |
| `REDIS_URL` | Redis接続URL | - | 自動設定 |
| `LOG_LEVEL` | ログレベル | - | `INFO` |

## 📊 監視・ログ

### ログの確認
```bash
# 構造化ログ（JSON形式）
docker-compose exec api tail -f /tmp/app.json.log

# コンソールログ
make logs

# 特定サービスのログ
docker-compose logs -f api
docker-compose logs -f worker
```

### メトリクス
- 記事生成成功率
- 文字数制御精度
- API応答時間
- WordPress投稿成功率

## 🔒 セキュリティ

- 全ての外部API呼び出しはHTTPS
- HTMLコンテンツの自動サニタイズ
- 入力データのバリデーション
- 秘密情報の環境変数管理
- ログからの機密情報除外

## 🧪 テスト

```bash
# 全テスト実行
make test

# カバレッジレポート
make test-coverage

# 特定テスト実行
docker-compose exec api pytest tests/test_generation.py -v
```