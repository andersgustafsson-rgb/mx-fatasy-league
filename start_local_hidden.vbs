' Startar lokal MX Fantasy utan synligt terminalfonster.
' Logg: instance\local_server.log
Option Explicit
Dim sh, fso, root, bat
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
bat = root & "\start_local_hidden.bat"
sh.CurrentDirectory = root
sh.Run """" & bat & """", 0, False
