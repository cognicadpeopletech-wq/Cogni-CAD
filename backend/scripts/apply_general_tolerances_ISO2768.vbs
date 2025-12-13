' ApplyISO2768_Tolerances.vbs
' Purpose: Applies ISO 2768 linear general tolerances to dimensions in a CATIA V5 drawing
' Version: 1.0 (hard-coded class = m, auto-reset colors = Yes)
Option Explicit

' --- CATIA V5 ENUMERATIONS ---
Const catDimFrameNone = 0

Sub CATMain()
    On Error Resume Next

    Dim oCATIA
    Set oCATIA = GetObject(, "CATIA.Application")
    If Err.Number <> 0 Then
        Err.Clear
        Set oCATIA = CreateObject("CATIA.Application")
        If Err.Number <> 0 Or oCATIA Is Nothing Then
            MsgBox "Error: CATIA Application not found and could not be started.", vbCritical, "Application Error"
            Exit Sub
        End If
    End If
    On Error GoTo 0

    If Not (TypeName(oCATIA.ActiveDocument) = "DrawingDocument") Then
        MsgBox "Error: This script must be run with an active Drawing Document.", vbCritical, "Document Error"
        Exit Sub
    End If

    Dim oDrawingDoc, oSelection
    Set oDrawingDoc = oCATIA.ActiveDocument
    Set oSelection = oDrawingDoc.Selection

    oCATIA.RefreshDisplay = False

    ' --- Backend data: ISO 2768 linear tolerances (mm) ---
    Dim arrNominalRanges()
    ReDim arrNominalRanges(7)
    arrNominalRanges(0) = 3
    arrNominalRanges(1) = 6
    arrNominalRanges(2) = 30
    arrNominalRanges(3) = 120
    arrNominalRanges(4) = 400
    arrNominalRanges(5) = 1000
    arrNominalRanges(6) = 2000
    arrNominalRanges(7) = 4000

    Dim arrISO_Tols
    ReDim arrISO_Tols(7, 3)

    ' Row 0: up to 3
    arrISO_Tols(0, 0) = 0.05   ' f
    arrISO_Tols(0, 1) = 0.10   ' m
    arrISO_Tols(0, 2) = 0.20   ' c
    arrISO_Tols(0, 3) = 0      ' v (not defined)

    ' Row 1: >3 up to 6
    arrISO_Tols(1, 0) = 0.05
    arrISO_Tols(1, 1) = 0.10
    arrISO_Tols(1, 2) = 0.30
    arrISO_Tols(1, 3) = 0.50

    ' Row 2: >6 up to 30
    arrISO_Tols(2, 0) = 0.10
    arrISO_Tols(2, 1) = 0.20
    arrISO_Tols(2, 2) = 0.50
    arrISO_Tols(2, 3) = 1.00

    ' Row 3: >30 up to 120
    arrISO_Tols(3, 0) = 0.15
    arrISO_Tols(3, 1) = 0.30
    arrISO_Tols(3, 2) = 0.80
    arrISO_Tols(3, 3) = 1.50

    ' Row 4: >120 up to 400
    arrISO_Tols(4, 0) = 0.20
    arrISO_Tols(4, 1) = 0.50
    arrISO_Tols(4, 2) = 1.20
    arrISO_Tols(4, 3) = 2.50

    ' Row 5: >400 up to 1000
    arrISO_Tols(5, 0) = 0.30
    arrISO_Tols(5, 1) = 0.80
    arrISO_Tols(5, 2) = 2.00
    arrISO_Tols(5, 3) = 4.00

    ' Row 6: >1000 up to 2000
    arrISO_Tols(6, 0) = 0.50
    arrISO_Tols(6, 1) = 1.20
    arrISO_Tols(6, 2) = 3.00
    arrISO_Tols(6, 3) = 6.00

    ' Row 7: >2000 up to 4000
    arrISO_Tols(7, 0) = 0        ' f not defined
    arrISO_Tols(7, 1) = 2.00
    arrISO_Tols(7, 2) = 4.00
    arrISO_Tols(7, 3) = 8.00

    ' --- USER INPUT (HARD-CODED) ---
    Dim sClassInput, lngClassIndex, iResetColor
    sClassInput = "m"
    Select Case LCase(Left(Trim(sClassInput), 1))
        Case "f": lngClassIndex = 0
        Case "m": lngClassIndex = 1
        Case "c": lngClassIndex = 2
        Case "v": lngClassIndex = 3
        Case Else
            MsgBox "Invalid hard-coded class. Use f, m, c or v.", vbExclamation, "Input Error"
            Exit Sub
    End Select

    ' Hard-coded color reset = Yes
    iResetColor = vbYes

    ' --- MAIN PROCESSING LOOP ---
    Dim oSheets, oSheet, oViews, oView, oDims, oDim
    Dim dblTol, dblRoundedTol
    Dim iBlueCount, iDefaultCount, iGreenCount
    Dim oVisProps, lRed, lGreen, lBlue
    iBlueCount = 0: iDefaultCount = 0: iGreenCount = 0
    Set oSheets = oDrawingDoc.Sheets

    For Each oSheet In oSheets
        Set oViews = oSheet.Views
        For Each oView In oViews
            Set oDims = oView.Dimensions
            If oDims.Count > 0 Then
                For Each oDim In oDims
                    If InStr(TypeName(oDim), "DrawingDimension") > 0 Then
                        oSelection.Clear
                        oSelection.Add oDim
                        Set oVisProps = oSelection.VisProperties
                        oVisProps.GetRealColor lRed, lGreen, lBlue

                        ' Ignore preserved green dimensions
                        If lRed = 0 And lGreen = 255 And lBlue = 0 Then
                            iGreenCount = iGreenCount + 1
                        ' Ignore Basic Dimensions (frame types)
                        ElseIf oDim.ValueFrame <> catDimFrameNone Then
                            ' skip basic dimensions
                        Else
                            Dim oDimValue
                            Set oDimValue = oDim.GetValue
                            Dim sBeforeText, sAfterText, sUpperText, sLowerText
                            sBeforeText = "": sAfterText = "": sUpperText = "": sLowerText = ""

                            On Error Resume Next
                            Err.Clear
                            oDimValue.GetBuiltText 1, sBeforeText, sAfterText, sUpperText, sLowerText
                            If Err.Number <> 0 Then
                                Err.Clear
                                ' fallback — try same call again (some API versions behave differently)
                                On Error Resume Next
                                oDimValue.GetBuiltText 1, sBeforeText, sAfterText, sUpperText, sLowerText
                                If Err.Number <> 0 Then
                                    Err.Clear
                                End If
                            End If
                            On Error GoTo 0

                            ' Skip reference dimensions (parentheses)
                            If InStr(sBeforeText, "(") = 0 And InStr(sAfterText, ")") = 0 Then
                                ' Count blue vs default colored dims for messaging (no TW/NW split for ISO2768)
                                If lRed = 0 And lGreen = 0 And lBlue = 255 Then
                                    iBlueCount = iBlueCount + 1
                                Else
                                    iDefaultCount = iDefaultCount + 1
                                End If

                                dblTol = GetISO2768Tolerance(oDimValue.Value, lngClassIndex, arrNominalRanges, arrISO_Tols)
                                If dblTol > 0 Then
                                    dblRoundedTol = RoundToNearest05(dblTol)
                                    ' Apply symmetric tolerances: type ANS_NUM2, upper = +dbl, lower = -dbl
                                    oDim.SetTolerances 1, "ANS_NUM2", "", "", dblRoundedTol, -dblRoundedTol, 0

                                    If iResetColor = vbYes Then
                                        Call SetObjectColor(oDim, oSelection, 0, 0, 0)
                                    End If
                                End If
                            End If
                        End If
                    End If
                Next
            End If
        Next
    Next

    oSelection.Clear
    oCATIA.RefreshDisplay = True

    Dim sFinalMsg
    sFinalMsg = "Tolerancing Complete." & vbCrLf & vbCrLf & _
                "Applied ISO 2768 class '" & sClassInput & "' to:" & vbCrLf & _
                "  - " & iBlueCount & " Non-default colored dimensions." & vbCrLf & _
                "  - " & iDefaultCount & " Default colored dimensions." & vbCrLf & vbCrLf & _
                "Safely ignored " & iGreenCount & " preserved (Green) dimensions." & vbCrLf

    If iResetColor = vbYes Then
        sFinalMsg = sFinalMsg & vbCrLf & "All " & (iBlueCount + iDefaultCount) & " processed dimensions have been reset to black." & vbCrLf
    End If

    sFinalMsg = sFinalMsg & vbCrLf & "-------------------- ACTION REQUIRED --------------------" & vbCrLf & _
                "Basic and Reference Dimensions were also safely ignored." & vbCrLf & _
                "The engineer MUST now manually review and apply specific requirements to all CRITICAL dimensions."

    MsgBox sFinalMsg, vbInformation, "Process Finished"
End Sub

Private Function GetISO2768Tolerance(ByVal dblNominal, ByVal lngClassIndex, ByRef arrRanges, ByRef arrTols)
    GetISO2768Tolerance = 0
    Dim i, iRow
    iRow = -1
    If dblNominal > 0 And dblNominal <= arrRanges(0) Then
        iRow = 0
    Else
        For i = 1 To UBound(arrRanges)
            If dblNominal > arrRanges(i - 1) And dblNominal <= arrRanges(i) Then
                iRow = i
                Exit For
            End If
        Next
    End If
    If iRow > -1 And lngClassIndex >= 0 And lngClassIndex <= 3 Then
        GetISO2768Tolerance = arrTols(iRow, lngClassIndex)
    End If
End Function

Private Function RoundToNearest05(ByVal dblValue)
    If dblValue = 0 Then
        RoundToNearest05 = 0
    Else
        RoundToNearest05 = Round(dblValue / 0.05, 0) * 0.05
    End If
End Function

Private Sub SetObjectColor(ByVal iObjectToColor, ByVal iSelection, ByVal R, ByVal G, ByVal B)
    On Error Resume Next
    iSelection.Clear
    iSelection.Add iObjectToColor
    Dim oVisProps
    Set oVisProps = iSelection.VisProperties
    oVisProps.SetRealColor R, G, B, 0
    If Err.Number <> 0 Then Err.Clear
    On Error GoTo 0
End Sub

' Run the main routine
CATMain
