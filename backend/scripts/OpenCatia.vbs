' OpenOrAttachCATIA.vbs
' Attaches to a running CATIA session or starts a new one.
' Shows CATIA, brings it to front, and (optionally) creates a new Part.

On Error Resume Next

Dim CATIA
' Try to attach to a running CATIA session
Set CATIA = GetObject(, "CATIA.Application")
If Err.Number <> 0 Then
    Err.Clear
    ' Launch a new CATIA session if not running
    Set CATIA = CreateObject("CATIA.Application")
    If Err.Number <> 0 Or TypeName(CATIA) = "Empty" Then
        WScript.Echo "❌ Failed to start or attach to CATIA: " & Err.Description
        WScript.Quit 1
    End If
End If

On Error GoTo 0

' Make CATIA visible and bring to front
CATIA.Visible = True

' Optional: create a new Part (comment out if not needed)
Dim docs, partDoc
Set docs = CATIA.Documents
Set partDoc = docs.Add("Part")

' Reframe active view if available
On Error Resume Next
CATIA.ActiveWindow.ActiveViewer.Reframe
On Error GoTo 0

WScript.Echo "✅ CATIA is ready."
WScript.Quit 0
