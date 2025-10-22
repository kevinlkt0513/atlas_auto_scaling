# Atlas 自動擴縮容腳本

一套整合在單一 Python 文件中的 MongoDB Atlas 自動擴縮容解決方案，基於 [MongoDB Atlas Scheduled Triggers](https://www.mongodb.com/developer/products/atlas/atlas-cluster-automation-using-scheduled-triggers/) 方法，使用 [Atlas Admin API v2](https://www.mongodb.com/docs/api/doc/atlas-admin-api-v2/)。提供高頻率監控、即時擴縮容決策和靈活的配置選項。

## 🚀 主要功能

### 核心特性
- **高頻率監控**：支援每分鐘級別的關鍵性能指標監控
- **零延遲擴容**：可配置 0 延遲的即時擴縮容響應
- **智能決策**：基於 CPU、連接數、IOPS、記憶體等多維度指標的智能擴縮容決策
- **靈活配置**：完全客製化的監控閾值和擴縮容策略
- **多通道警報**：支援 Webhook、Email、Slack 等多種警報方式
- **Atlas API v2 支援**：使用最新的 Atlas Admin API v2 和正確的認證方法

### 解決的問題
- **骨牌效應防護**：防止系統流量激增導致的節點資源耗盡
- **Atlas 內建限制**：克服 Atlas 內建自動擴縮容 10 分鐘延遲的限制
- **業務靈活性**：提供客戶業務場景的最佳實踐配置

## 🏗️ 系統架構

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   配置管理      │    │   監控模組      │    │   擴縮容引擎    │
│   Config       │    │   Monitor       │    │   Scaler        │
│   Manager      │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   Atlas API     │
                    │   Client        │
                    └─────────────────┘
                                 │
                    ┌─────────────────┐
                    │   MongoDB       │
                    │   Atlas         │
                    └─────────────────┘
```

### 核心模組

1. **配置管理 (config.py)**
   - 集中管理所有配置參數
   - 支援環境變數和配置文件
   - 配置驗證和錯誤處理

2. **Atlas API 客戶端 (atlas_client.py)**
   - 完整的 Atlas Admin API 封裝
   - 認證和簽名處理
   - 指標數據收集

3. **監控模組 (monitor.py)**
   - 實時指標收集和處理
   - 健康狀態評估
   - 趨勢分析和警報生成

4. **擴縮容引擎 (scaler.py)**
   - 智能擴縮容決策
   - 冷卻期管理
   - 擴縮容歷史追蹤

5. **警報管理 (alerts.py)**
   - 多通道警報發送
   - 警報模板和格式化
   - 警報歷史管理

## 📋 安裝和配置

### 環境要求
- Python 3.8+
- MongoDB Atlas 項目和 API 密鑰
- 網路連接到 Atlas API

### 安裝步驟

1. **下載腳本**
```bash
# 下載單一 Python 文件
wget https://raw.githubusercontent.com/yourcompany/atlas-auto-scaling/main/atlas_auto_scaling.py
```

2. **安裝依賴**
```bash
pip install requests
```

3. **創建配置**
```bash
python atlas_auto_scaling.py --init-config
# 編輯 config.json 填入您的 Atlas API 憑證
```

4. **設定環境變數（可選）**
```bash
export ATLAS_PUBLIC_KEY="your_public_key"
export ATLAS_PRIVATE_KEY="your_private_key"
export ATLAS_PROJECT_ID="your_project_id"
```

### 配置說明

#### 監控配置
```json
{
  "monitoring": {
    "check_interval": 60,           // 檢查間隔（秒）
    "cpu_threshold_high": 80.0,     // CPU 高閾值（%）
    "cpu_threshold_low": 30.0,       // CPU 低閾值（%）
    "connection_threshold_high": 1000,  // 連接數高閾值
    "connection_threshold_low": 100,    // 連接數低閾值
    "iops_threshold_high": 1000,    // IOPS 高閾值
    "iops_threshold_low": 100,       // IOPS 低閾值
    "memory_threshold_high": 85.0,   // 記憶體高閾值（%）
    "memory_threshold_low": 40.0     // 記憶體低閾值（%）
  }
}
```

#### 擴縮容配置
```json
{
  "scaling": {
    "enabled": true,                // 啟用自動擴縮容
    "scale_up_cooldown": 0,         // 擴容冷卻期（秒，0=無延遲）
    "scale_down_cooldown": 300,     // 縮容冷卻期（秒）
    "max_scale_up_per_hour": 3,     // 每小時最大擴容次數
    "max_scale_down_per_hour": 2,   // 每小時最大縮容次數
    "min_instance_size": "M10",      // 最小實例大小
    "max_instance_size": "M80",     // 最大實例大小
    "scale_up_step": "M20",         // 擴容步長
    "scale_down_step": "M10"        // 縮容步長
  }
}
```

## 🚀 使用方法

### 基本使用

1. **連續監控模式**
```bash
python atlas_auto_scaling.py --mode continuous
```

2. **單次檢查模式**
```bash
python atlas_auto_scaling.py --mode single
```

3. **監控特定集群**
```bash
python atlas_auto_scaling.py --clusters cluster1 cluster2
```

### 進階功能

1. **查看狀態報告**
```bash
python atlas_auto_scaling.py --status
```

2. **強制擴縮容**
```bash
python atlas_auto_scaling.py --force-scale cluster1:M40
```

3. **禁用/啟用擴縮容**
```bash
python atlas_auto_scaling.py --disable-scaling cluster1
python atlas_auto_scaling.py --enable-scaling cluster1
```

### 最佳實踐配置

#### 高流量場景
```json
{
  "monitoring": {
    "check_interval": 30,           // 更頻繁的檢查
    "cpu_threshold_high": 70.0,     // 更敏感的 CPU 閾值
    "scale_up_cooldown": 0          // 零延遲擴容
  },
  "scaling": {
    "max_scale_up_per_hour": 5,     // 允許更頻繁的擴容
    "scale_up_step": "M30"          // 更大的擴容步長
  }
}
```

#### 成本優化場景
```json
{
  "monitoring": {
    "cpu_threshold_low": 20.0,      // 更積極的縮容
    "scale_down_cooldown": 600      // 較長的縮容冷卻期
  },
  "scaling": {
    "max_scale_down_per_hour": 1    // 限制縮容頻率
  }
}
```

## 📊 監控指標

### 支援的指標
- **CPU 使用率**：處理器使用百分比
- **連接數**：當前資料庫連接數
- **IOPS**：每秒輸入/輸出操作數
- **記憶體使用率**：記憶體使用百分比

### 指標收集頻率
- 預設：每分鐘收集一次
- 可配置：10 秒到 1 小時
- 歷史數據：保留最近 100 個數據點

## 🔧 故障排除

### 常見問題

1. **API 連接失敗**
   - 檢查 Atlas API 憑證
   - 確認網路連通性
   - 驗證專案 ID

2. **擴縮容失敗**
   - 檢查集群狀態
   - 確認實例大小限制
   - 查看冷卻期設定

3. **警報未發送**
   - 檢查警報配置
   - 驗證 Webhook URL
   - 確認 SMTP 設定

### 日誌分析
```bash
# 查看應用日誌
tail -f atlas_scaling.log

# 查看錯誤日誌
grep ERROR atlas_scaling.log
```

## 🔒 安全考量

### API 安全
- 使用環境變數存儲敏感憑證
- 定期輪換 API 密鑰
- 限制 API 權限範圍

### 網路安全
- 使用 HTTPS 連接
- 配置防火牆規則
- 監控異常 API 調用

## 📈 性能優化

### 監控優化
- 調整檢查間隔平衡性能和成本
- 使用指標聚合減少 API 調用
- 實施指數退避重試機制

### 擴縮容優化
- 配置適當的冷卻期
- 使用預測性擴容
- 實施漸進式擴容策略

## 🤝 貢獻指南

### 開發環境設定
```bash
# 安裝開發依賴
pip install -r requirements.txt
pip install pytest black flake8 mypy

# 運行測試
pytest

# 代碼格式化
black .

# 代碼檢查
flake8 .
mypy .
```

### 提交規範
- 使用清晰的提交訊息
- 包含測試用例
- 更新文檔

## 📄 授權

本專案採用 MIT 授權條款。詳見 [LICENSE](LICENSE) 文件。

## 📞 支援

- 問題回報：[GitHub Issues](https://github.com/yourcompany/atlas-auto-scaling/issues)
- 文檔：[專案 Wiki](https://github.com/yourcompany/atlas-auto-scaling/wiki)
- 聯絡：[kevin.kotsunleung@gmail.com](mailto:kevin.kotsunleung@gmail.com)

---

**注意**：本腳本為客製化解決方案，請根據您的具體需求調整配置參數。建議在生產環境使用前進行充分測試。
