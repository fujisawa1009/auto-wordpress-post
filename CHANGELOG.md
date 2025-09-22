# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-09-22

### Added

#### Phase 1: 基盤構築
- Docker/Docker Compose環境設定
- PostgreSQL/Redisコンテナ構成
- FastAPI アプリケーション基盤
- SQLAlchemy データベースモデル (Article, Job, Taxonomy)
- Alembic マイグレーション設定
- Pydantic スキーマ定義
- Celery/Redis非同期ワーカー基盤
- 構造化ログ出力システム
- HTMLサニタイズユーティリティ

#### Phase 2: 記事生成エンジン
- Perplexity API クライアント実装
- 記事アウトライン生成機能 (H2×6-9個、H3×2-3個)
- セクション別コンテンツ生成
- 記事マージ・最終化システム
- 文字数制御・自動調整機能 (9,000-11,000字)
- プロンプトエンジニアリングテンプレート
- エラーハンドリング・リトライ機構 (tenacity)
- 冪等性実装 (入力ハッシュベース)

#### Phase 3: WordPress連携
- WordPress REST API クライアント
- カテゴリ・タグ解決システム
- WordPress投稿作成機能 (下書き/公開/予約)
- メディアアップロード機能
- HTMLプレビューテンプレートシステム
- 日本語slug生成機能
- 認証・認可 (Application Password)
- タクソノミー自動作成機能

### Features

- **AI記事生成**: Perplexity APIを使用した約10,000字の記事生成
- **WordPress連携**: 下書き/公開/予約投稿の自動化
- **プレビュー機能**: 安全なHTMLプレビュー表示
- **文字数制御**: 目標文字数への自動調整
- **冪等性**: 同一入力による重複生成防止
- **非同期処理**: Celeryによるバックグラウンド処理
- **エラー処理**: 堅牢なリトライ・フォールバック機構
- **構造化ログ**: JSON形式での詳細ログ出力
- **タクソノミー管理**: WordPressカテゴリ・タグの自動同期

### API Endpoints

- `POST /api/articles/generate` - 記事生成開始
- `GET /api/articles/{id}` - 記事取得・ステータス確認
- `POST /api/articles/{id}/publish` - WordPress投稿
- `POST /api/articles/{id}/regenerate` - 記事再生成
- `DELETE /api/articles/{id}` - 記事削除
- `GET /api/taxonomies/sync` - タクソノミー同期
- `GET /api/taxonomies/categories` - カテゴリ一覧
- `GET /api/taxonomies/tags` - タグ一覧
- `GET /preview/{id}` - HTMLプレビュー表示
- `GET /health` - ヘルスチェック

### Technical Stack

- **Backend**: FastAPI, Python 3.12
- **Database**: PostgreSQL 16
- **Queue**: Redis 7, Celery
- **AI**: Perplexity API
- **CMS**: WordPress REST API
- **Containerization**: Docker, Docker Compose
- **Migration**: Alembic
- **Testing**: pytest (準備済み)
- **Logging**: structlog, python-json-logger

### Configuration

#### Environment Variables
- `PPLX_API_KEY` - Perplexity API キー
- `WP_BASE_URL` - WordPress サイトURL
- `WP_USERNAME` - WordPress ユーザー名
- `WP_APPLICATION_PASSWORD` - WordPress アプリケーションパスワード
- `DATABASE_URL` - PostgreSQL接続URL
- `REDIS_URL` - Redis接続URL

#### Character Count Control
- Target: 10,000字 (9,000-11,000字の範囲)
- Automatic expansion for short content
- Automatic condensation for long content
- HTML tag sanitization

#### Security Features
- Input validation (Pydantic)
- HTML sanitization (bleach)
- Secret management (environment variables)
- HTTPS requirement for external APIs

### Performance
- Concurrent section generation
- Async/await pattern throughout
- Database connection pooling
- Redis caching for taxonomies
- Exponential backoff retry logic

### Monitoring
- Structured JSON logging
- Perplexity API call metrics
- WordPress API success rates
- Character count accuracy tracking
- Generation time monitoring

## [Unreleased]

### Planned Features
- 画像自動生成・WordPress登録
- 多言語対応 (日本語→英語)
- 内部リンク自動サジェスト
- SEO品質スコア機能
- 記事テンプレート機能
- GraphQL API対応
- Kubernetes対応