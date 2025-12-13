'*************************************************************
' CATIA VBS Script: Toggle Lock/Unlock for Drawing Views
' Description: Locks or unlocks selected drawing views in the
'              active sheet. If no view is selected, it toggles
'              all views except the Background View.
'*************************************************************
 
On Error Resume Next
 
' 🔹 Connect to running CATIA instance
Set CATIA = GetObject(, "CATIA.Application")
If CATIA Is Nothing Then
    MsgBox "CATIA is not running. Please open CATIA and try again.", vbExclamation, "CATIA VBS"
    WScript.Quit
End If
Err.Clear
On Error GoTo 0
 
' 🔹 Ensure a document is open
If CATIA.Documents.Count = 0 Then
    MsgBox "No documents are open. Please open a drawing file.", vbExclamation, "CATIA VBS"
    WScript.Quit
End If
 
' 🔹 Ensure the active document is a Drawing
Set doc = CATIA.ActiveDocument
If doc Is Nothing Then
    MsgBox "No active document found.", vbExclamation, "CATIA VBS"
    WScript.Quit
End If
 
If TypeName(doc) <> "DrawingDocument" Then
    MsgBox "Please run this script from a Drawing document.", vbExclamation, "CATIA VBS"
    WScript.Quit
End If
 
' 🔹 Get the active sheet and its views
Set sh = doc.Sheets.ActiveSheet
Set views = sh.Views
 
' 🔹 Get current selection
Set sel = doc.Selection
 
Dim foundViews()
foundCount = 0
 
' 🔹 Collect selected DrawingView objects if any
If sel.Count > 0 Then
    For i = 1 To sel.Count
        Set selObj = Nothing
        On Error Resume Next
        Set selObj = sel.Item(i).Value
        On Error GoTo 0
        If Not selObj Is Nothing Then
            If TypeName(selObj) = "DrawingView" Then
                foundCount = foundCount + 1
                ReDim Preserve foundViews(foundCount)
                Set foundViews(foundCount) = selObj
            End If
        End If
    Next
End If
 
' 🔹 If no selected views, toggle all (except Background View)
If foundCount = 0 Then
    For v = 1 To views.Count
        Set dv = views.Item(v)
        If LCase(dv.Name) <> LCase("Background View") Then
            foundCount = foundCount + 1
            ReDim Preserve foundViews(foundCount)
            Set foundViews(foundCount) = dv
        End If
    Next
End If
 
' 🔹 If still none found
If foundCount = 0 Then
    MsgBox "No drawing views found to process.", vbExclamation, "CATIA VBS"
    WScript.Quit
End If
 
' 🔹 Toggle lock/unlock status
lockedCount = 0
unlockedCount = 0
 
For k = 1 To foundCount
    On Error Resume Next
    If foundViews(k).LockStatus = True Then
        foundViews(k).LockStatus = False
        unlockedCount = unlockedCount + 1
    Else
        foundViews(k).LockStatus = True
        lockedCount = lockedCount + 1
    End If
    On Error GoTo 0
Next
 
' 🔹 Display summary
MsgBox "✅ Updated " & foundCount & " view(s):" & vbCrLf & _
       "🔒 Locked: " & lockedCount & vbCrLf & _
       "🔓 Unlocked: " & unlockedCount, vbInformation, "CATIA VBS - Toggle View Lock"
 
' 🔹 Cleanup
Set dv = Nothing
Set selObj = Nothing
Set sel = Nothing
Set views = Nothing
Set sh = Nothing
Set doc = Nothing
Set CATIA = Nothing