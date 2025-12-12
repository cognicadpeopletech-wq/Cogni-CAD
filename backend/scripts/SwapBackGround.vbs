'*************************************************************

' CATIA VBS Script: Toggle Between Working View and Background View

' Description: Switches the active view in a drawing between

'              the working view and the background view.

'*************************************************************
 
On Error Resume Next
 
' 🔹 Connect to running CATIA instance

Set CATIA = GetObject(, "CATIA.Application")

If Err.Number <> 0 Then

    MsgBox "Could not connect to CATIA. Please make sure CATIA is running.", vbExclamation, "CATIA VBS"

    WScript.Quit

End If

Err.Clear

On Error GoTo 0
 
' 🔹 Check if any document is open

If CATIA.Documents.Count = 0 Then

    MsgBox "No document is open. Please open a drawing file.", vbExclamation, "CATIA VBS"

    WScript.Quit

End If
 
' 🔹 Check if active document is a drawing

If TypeName(CATIA.ActiveDocument) <> "DrawingDocument" Then

    MsgBox "Active document is not a Drawing. Please open a Drawing before running this script.", vbExclamation, "CATIA VBS"

    WScript.Quit

End If
 
' 🔹 Get active drawing document and sheet

Set drawingDocument = CATIA.ActiveDocument

Set drawingSheet = drawingDocument.Sheets.ActiveSheet

Set drawingViews = drawingSheet.Views

Set activeView = drawingViews.ActiveView
 
' 🔹 Try to get the background view

On Error Resume Next

Set backgroundView = drawingViews.Item("Background View")

On Error GoTo 0
 
' 🔹 Toggle between Background and Working Views

If Not backgroundView Is Nothing Then

    If activeView.Name = "Background View" Then

        ' Switch to first non-background (working) view

        For i = 1 To drawingViews.Count

            If drawingViews.Item(i).Name <> "Background View" Then

                drawingViews.Item(i).Activate

                MsgBox "✅ Switched to Working Views.", vbInformation, "CATIA VBS"

                Exit For

            End If

        Next

    Else

        ' Switch to background view

        backgroundView.Activate

        MsgBox "✅ Switched to Sheet Background.", vbInformation, "CATIA VBS"

    End If

Else

    MsgBox "⚠️ No Background View found in this sheet.", vbExclamation, "CATIA VBS"

End If
 
' 🔹 Cleanup

Set backgroundView = Nothing

Set activeView = Nothing

Set drawingViews = Nothing

Set drawingSheet = Nothing

Set drawingDocument = Nothing

Set CATIA = Nothing