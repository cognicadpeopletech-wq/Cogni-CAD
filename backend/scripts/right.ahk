#SingleInstance Force
SetTitleMatchMode 2

; Get the active window ID
WinGet, activeWindow, ID, A

if (activeWindow = "")
    ExitApp

; Ensure window is not minimized
WinRestore, ahk_id %activeWindow%

; Small delay to ensure window is ready
Sleep, 100

; Calculate half screen width
halfWidth := A_ScreenWidth / 2

; Move active window to RIGHT half of the screen
WinMove, ahk_id %activeWindow%, , %halfWidth%, 0, %halfWidth%, %A_ScreenHeight%

return
