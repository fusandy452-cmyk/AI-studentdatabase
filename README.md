# AI 留學顧問 - 資料庫服務

這是 AI 留學顧問系統的獨立資料庫服務，負責處理所有資料庫相關操作。

## 功能

- 用戶資料管理
- 用戶設定資料管理
- 聊天記錄儲存
- 使用統計追蹤
- 資料庫備份

## API 端點

### 健康檢查
- `GET /health` - 檢查服務狀態

### 用戶管理
- `POST /api/users` - 儲存用戶資料
- `GET /api/users/<user_id>` - 獲取用戶資料
- `GET /api/users/<user_id>/profiles` - 獲取用戶的設定資料

### 設定資料管理
- `POST /api/profiles` - 儲存用戶設定資料
- `GET /api/profiles/<profile_id>` - 獲取設定資料
- `PUT /api/profiles/<profile_id>` - 更新設定資料

### 聊天記錄
- `POST /api/messages` - 儲存聊天記錄
- `GET /api/messages/<profile_id>` - 獲取聊天記錄

### 使用統計
- `POST /api/stats` - 儲存使用統計
- `GET /api/stats` - 獲取使用統計

### 備份
- `POST /api/backup` - 創建資料庫備份

## 部署

1. 將此專案推送到 GitHub
2. 在 Zeabur 中連接 GitHub 倉庫
3. 部署到 Zeabur 平台

## 環境變數

- `PORT` - 服務端口 (預設: 5000)
- `ZEABUR_PERSISTENT_DIR` - 持久化目錄 (預設: /data)

## 資料庫

使用 SQLite 資料庫，支援：
- WAL 模式提高並發性
- 自動備份機制
- 持久化儲存
