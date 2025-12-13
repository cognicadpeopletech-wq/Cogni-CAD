#SingleInstance Force
SetTitleMatchMode 2

; Get the active window ID
WinGet, activeWindow, ID, A

if (activeWindow = "")
    ExitApp

; Small delay to ensure window is ready
Sleep, 100

; Maximize the active window
WinMaximize, ahk_id %activeWindow%

return
