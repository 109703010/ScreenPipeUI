# **ScreenRecall**

ScreenRecall 是一個結合 **ScreenPipe** 錄製功能與 **Ollama** 本地視覺大語言模型（Vision LLM）的螢幕內容檢索工具。它能幫助您像翻閱日誌一樣，找回遺忘在螢幕某處的資訊。

## **✨ 核心功能 (Features)**

* **關鍵字回顧 (Keyword Recall)**：  
  輸入特定關鍵字，系統將檢索 ScreenPipe 資料庫，精確找出過去瀏覽過、包含該內容的歷史紀錄。  
* **時段摘要 (Time-period Summary)**：  
  選定一段特定的時間區間，利用 AI 分析該段時間的螢幕畫面，為您自動總結該時段的工作重點與活動摘要。

## **📋 前置準備 (Prerequisites)**

在開始安裝 ScreenRecall 之前，請確保您的系統已完成以下配置：

1. **ScreenPipe CLI**:  
   * 確保電腦已安裝 [ScreenPipe](https://github.com/screenpipe/screenpipe)。  
   * 本專案提供 run\_screenpipe.vbs 腳本，可用於背景靜默啟動錄製服務。  
2. **Ollama**:  
   * 請確保已安裝 Ollama，執行時點兩下啟動即可。  
   * **重要**：由於本專案涉及螢幕畫面分析，您必須安裝支援 **Vision** 的模型（例如 llava, moondream 或 llama3.2-vision）。  
   * *指令範例：* ollama run llava

## **🚀 安裝步驟 (Installation)**

請依照下列步驟建立虛擬環境並安裝必要套件：

### **1\. 建立並啟動虛擬環境**

在專案根目錄下執行：

\# 建立虛擬環境  
```
python \-m venv .venv
```

\# 啟動虛擬環境 (Windows)  
```
.\\.venv\\Scripts\\activate
```

### **2\. 安裝依賴套件**

在虛擬環境啟動的狀態下執行：
```
pip install \-r requirements.txt
```

## **🖥️ 使用說明 (Usage)**

### **快速啟動 (一般模式)**

如果您只想單純使用 App 功能，直接執行：

* **RecallUI.vbs**  
  *這會為您啟動使用者介面，提供乾淨的操作體驗。*

### **開發者監控模式 (Debug Mode)**

如果您想要看 Server 的運作狀況（同時查看 Terminal 輸出與網頁跳轉）：

1. 找到 **runUI.ps1**。  
2. **右鍵點擊** 並選擇 **「以 PowerShell 執行」**。  
   *此操作會同時開啟終端機與瀏覽器介面，方便監控後端運作邏輯。*

## **🛠️ 常見問題**

* **摘要功能無回應？** 請確認您的 Ollama 已經下載並能成功運行 **Vision Model**。  
* **找不到歷史資料？** 請確認 run\_screenpipe.vbs 是否正在背景執行，ScreenPipe 需要時間累積錄製資料。