'*************************************************************
' CATIA VBS Script: Toggle View Frame Visibility for Drawings
' Description: Turns ON or OFF the View Frames for all views
'*************************************************************
 
On Error Resume Next
 
' 🔹 Connect to running CATIA instance
Set CATIA = GetObject(, "CATIA.Application")
If Err.Number <> 0 Then
    MsgBox "Could not get CATIA application. Make sure CATIA is running.", vbExclamation, "Error"
    WScript.Quit
End If
Err.Clear
On Error GoTo 0
 
' 🔹 Get active document
Set doc = CATIA.ActiveDocument
If doc Is Nothing Then
    MsgBox "No active document found. Open a drawing and try again.", vbExclamation, "Error"
    WScript.Quit
End If
 
' 🔹 Ensure the active document is a drawing
If InStr(1, UCase(doc.Name), "CATDRAWING") = 0 Then
    MsgBox "Active document is not a drawing. Please open a .CATDrawing and try again.", vbExclamation, "Error"
    WScript.Quit
End If
 
' 🔹 Check for sheets
sheetCount = 0
On Error Resume Next
sheetCount = doc.Sheets.Count
If Err.Number <> 0 Or sheetCount = 0 Then
    MsgBox "No sheets found in the drawing or unable to access Sheets collection.", vbExclamation, "Error"
    WScript.Quit
End If
Err.Clear
On Error GoTo 0
 
' 🔹 Detect if any view frame is currently ON
anyFrameOn = False
Dim i, j
Dim sh, vw
 
For i = 1 To doc.Sheets.Count
    Set sh = doc.Sheets.Item(i)
    If Not sh Is Nothing Then
        For j = 1 To sh.Views.Count
            Set vw = sh.Views.Item(j)
            If Not vw Is Nothing Then
                On Error Resume Next
                val = vw.FrameVisualization
                If Err.Number = 0 Then
                    If CBool(val) = True Then
                        anyFrameOn = True
                        Exit For
                    End If
                End If
                Err.Clear
                On Error GoTo 0
            End If
        Next
        If anyFrameOn = True Then Exit For
    End If
Next
 
' 🔹 Determine target state (toggle)
targetState = Not anyFrameOn
 
' 🔹 Apply the change to all views
successCount = 0
failCount = 0
 
For i = 1 To doc.Sheets.Count
    Set sh = doc.Sheets.Item(i)
    If Not sh Is Nothing Then
        For j = 1 To sh.Views.Count
            Set vw = sh.Views.Item(j)
            If Not vw Is Nothing Then
                On Error Resume Next
                vw.FrameVisualization = targetState
                If Err.Number = 0 Then
                    successCount = successCount + 1
                Else
                    failCount = failCount + 1
                    Err.Clear
                End If
                On Error GoTo 0
            End If
        Next
    End If
Next
 
' 🔹 Refresh CATIA window
On Error Resume Next
CATIA.ActiveWindow.ActiveViewer.Repaint
On Error GoTo 0
 
' 🔹 Display result
Dim sText
If targetState = False Then
    sText = "✅ View Frames are now OFF for " & CStr(successCount) & " view(s)."
Else
    sText = "✅ View Frames are now ON for " & CStr(successCount) & " view(s)."
End If
 
If failCount > 0 Then
    sText = sText & vbCrLf & "⚠️ Note: " & CStr(failCount) & " view(s) could not be changed (property not available)."
End If
 
MsgBox sText, vbInformation, "CATIA View Frame Toggle"
 
' 🔹 Cleanup
Set vw = Nothing
Set sh = Nothing
Set doc = Nothing
Set CATIA = Nothing