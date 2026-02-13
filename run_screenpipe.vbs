Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "powershell.exe -NoProfile -Command ""screenpipe --fps 0.5 --video-quality low""", 0, False