Dim CATIA
On Error Resume Next

' Connect to running CATIA instance
Set CATIA = GetObject(, "CATIA.Application")

If Err.Number <> 0 Then
    MsgBox "CATIA is not running!"
    WScript.Quit
End If



' Run CATScript
CATIA.SystemService.ExecuteScript macroPath, 1, "CATMain"

WScript.Sleep 2000

' Optional: Close CATIA
CATIA.Quit

Set CATIA = Nothing
