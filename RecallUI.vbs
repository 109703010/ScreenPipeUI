Set WshShell = CreateObject("WScript.Shell")

' 獲取腳本所在的當前目錄，確保相對路徑正確
strPath = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strPath

' 啟動指令：直接呼叫虛擬環境內的 python.exe 來執行 streamlit
' 這樣就不需要額外跑 .venv\Scripts\Activate.ps1
dim command
command = "cmd /c .venv\Scripts\python.exe -m streamlit run app.py --server.headless true"

' 0 代表隱藏視窗執行
WshShell.Run command, 0

' 等待 3 秒讓 Streamlit Server 啟動
WScript.Sleep 3000

' 用 App 模式開啟瀏覽器
WshShell.Run "msedge --app=http://localhost:8501", 1