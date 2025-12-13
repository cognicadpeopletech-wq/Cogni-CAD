' ApplyISO20457_NoPopups.vbs
' Purpose: Applies general tolerances to all dimensions in a CATIA V5 drawing
'          based on the ISO 20457 standard for plastic parts.
' Version: 1.1 (silenced UI; defaults: Material=1, MasterTG=5, ResetColor=Yes)
Option Explicit

' --- CATIA V5 ENUMERATIONS ---
Const catDimFrameNone = 0

Sub CATMain()
    On Error Resume Next

    Dim oCATIA
    ' Try to get running CATIA; if none, try to start it. If that fails, silently exit.
    Set oCATIA = GetObject(, "CATIA.Application")
    If Err.Number <> 0 Then
        Err.Clear
        Set oCATIA = CreateObject("CATIA.Application")
        If Err.Number <> 0 Or oCATIA Is Nothing Then
            Exit Sub
        End If
    End If
    On Error GoTo 0

    If Not (TypeName(oCATIA.ActiveDocument) = "DrawingDocument") Then
        ' Silent exit if not a drawing document
        Exit Sub
    End If

    Dim oDrawingDoc, oSelection
    Set oDrawingDoc = oCATIA.ActiveDocument
    Set oSelection = oDrawingDoc.Selection

    oCATIA.RefreshDisplay = False

    ' --- Backend data ---
    Dim dictMaterialMap
    Set dictMaterialMap = CreateObject("Scripting.Dictionary")
    dictMaterialMap.Add "1", 5 ' PC, PC/ABS -> TG5
    dictMaterialMap.Add "2", 6 ' PA-GF, PBT-GF
    dictMaterialMap.Add "3", 7 ' PP, PP-Talc
    dictMaterialMap.Add "4", 6 ' POM, PA66
    dictMaterialMap.Add "5", 4 ' PEEK, PPSU

    Dim arrNominalRanges(11)
    arrNominalRanges(0) = 3: arrNominalRanges(1) = 6: arrNominalRanges(2) = 10: arrNominalRanges(3) = 18
    arrNominalRanges(4) = 30: arrNominalRanges(5) = 50: arrNominalRanges(6) = 80: arrNominalRanges(7) = 120
    arrNominalRanges(8) = 180: arrNominalRanges(9) = 250: arrNominalRanges(10) = 315: arrNominalRanges(11) = 400

    Dim arrTW_Tolerances(11, 4), arrNW_Tolerances(11, 4)
    ' Tool-Specific (TW) table: columns represent TG4..TG8
    arrTW_Tolerances(0, 0) = 0.03: arrTW_Tolerances(0, 1) = 0.05: arrTW_Tolerances(0, 2) = 0.07: arrTW_Tolerances(0, 3) = 0.13: arrTW_Tolerances(0, 4) = 0.20
    arrTW_Tolerances(1, 0) = 0.05: arrTW_Tolerances(1, 1) = 0.08: arrTW_Tolerances(1, 2) = 0.12: arrTW_Tolerances(1, 3) = 0.20: arrTW_Tolerances(1, 4) = 0.30
    arrTW_Tolerances(2, 0) = 0.08: arrTW_Tolerances(2, 1) = 0.11: arrTW_Tolerances(2, 2) = 0.18: arrTW_Tolerances(2, 3) = 0.29: arrTW_Tolerances(2, 4) = 0.45
    arrTW_Tolerances(3, 0) = 0.09: arrTW_Tolerances(3, 1) = 0.14: arrTW_Tolerances(3, 2) = 0.22: arrTW_Tolerances(3, 3) = 0.35: arrTW_Tolerances(3, 4) = 0.55
    arrTW_Tolerances(4, 0) = 0.11: arrTW_Tolerances(4, 1) = 0.17: arrTW_Tolerances(4, 2) = 0.26: arrTW_Tolerances(4, 3) = 0.42: arrTW_Tolerances(4, 4) = 0.65
    arrTW_Tolerances(5, 0) = 0.13: arrTW_Tolerances(5, 1) = 0.20: arrTW_Tolerances(5, 2) = 0.31: arrTW_Tolerances(5, 3) = 0.50: arrTW_Tolerances(5, 4) = 0.80
    arrTW_Tolerances(6, 0) = 0.15: arrTW_Tolerances(6, 1) = 0.23: arrTW_Tolerances(6, 2) = 0.37: arrTW_Tolerances(6, 3) = 0.60: arrTW_Tolerances(6, 4) = 0.95
    arrTW_Tolerances(7, 0) = 0.23: arrTW_Tolerances(7, 1) = 0.36: arrTW_Tolerances(7, 2) = 0.57: arrTW_Tolerances(7, 3) = 0.90: arrTW_Tolerances(7, 4) = 1.40
    arrTW_Tolerances(8, 0) = 0.32: arrTW_Tolerances(8, 1) = 0.50: arrTW_Tolerances(8, 2) = 0.80: arrTW_Tolerances(8, 3) = 1.25: arrTW_Tolerances(8, 4) = 2.00
    arrTW_Tolerances(9, 0) = 0.35: arrTW_Tolerances(9, 1) = 0.58: arrTW_Tolerances(9, 2) = 0.93: arrTW_Tolerances(9, 3) = 1.45: arrTW_Tolerances(9, 4) = 2.30
    arrTW_Tolerances(10, 0) = 0.41: arrTW_Tolerances(10, 1) = 0.65: arrTW_Tolerances(10, 2) = 1.05: arrTW_Tolerances(10, 3) = 1.60: arrTW_Tolerances(10, 4) = 2.60
    arrTW_Tolerances(11, 0) = 0.45: arrTW_Tolerances(11, 1) = 0.70: arrTW_Tolerances(11, 2) = 1.15: arrTW_Tolerances(11, 3) = 1.80: arrTW_Tolerances(11, 4) = 2.85

    ' Non-Tool-Specific (NW) table
    arrNW_Tolerances(0, 0) = 0.05: arrNW_Tolerances(0, 1) = 0.08: arrNW_Tolerances(0, 2) = 0.12: arrNW_Tolerances(0, 3) = 0.20: arrNW_Tolerances(0, 4) = 0.30
    arrNW_Tolerances(1, 0) = 0.08: arrNW_Tolerances(1, 1) = 0.11: arrNW_Tolerances(1, 2) = 0.18: arrNW_Tolerances(1, 3) = 0.29: arrNW_Tolerances(1, 4) = 0.45
    arrNW_Tolerances(2, 0) = 0.09: arrNW_Tolerances(2, 1) = 0.14: arrNW_Tolerances(2, 2) = 0.22: arrNW_Tolerances(2, 3) = 0.35: arrNW_Tolerances(2, 4) = 0.55
    arrNW_Tolerances(3, 0) = 0.11: arrNW_Tolerances(3, 1) = 0.17: arrNW_Tolerances(3, 2) = 0.26: arrNW_Tolerances(3, 3) = 0.42: arrNW_Tolerances(3, 4) = 0.65
    arrNW_Tolerances(4, 0) = 0.13: arrNW_Tolerances(4, 1) = 0.20: arrNW_Tolerances(4, 2) = 0.31: arrNW_Tolerances(4, 3) = 0.50: arrNW_Tolerances(4, 4) = 0.80
    arrNW_Tolerances(5, 0) = 0.15: arrNW_Tolerances(5, 1) = 0.23: arrNW_Tolerances(5, 2) = 0.37: arrNW_Tolerances(5, 3) = 0.60: arrNW_Tolerances(5, 4) = 0.95
    arrNW_Tolerances(6, 0) = 0.23: arrNW_Tolerances(6, 1) = 0.36: arrNW_Tolerances(6, 2) = 0.57: arrNW_Tolerances(6, 3) = 0.90: arrNW_Tolerances(6, 4) = 1.40
    arrNW_Tolerances(7, 0) = 0.32: arrNW_Tolerances(7, 1) = 0.50: arrNW_Tolerances(7, 2) = 0.80: arrNW_Tolerances(7, 3) = 1.25: arrNW_Tolerances(7, 4) = 2.00
    arrNW_Tolerances(8, 0) = 0.35: arrNW_Tolerances(8, 1) = 0.58: arrNW_Tolerances(8, 2) = 0.93: arrNW_Tolerances(8, 3) = 1.45: arrNW_Tolerances(8, 4) = 2.30
    arrNW_Tolerances(9, 0) = 0.41: arrNW_Tolerances(9, 1) = 0.65: arrNW_Tolerances(9, 2) = 1.05: arrNW_Tolerances(9, 3) = 1.60: arrNW_Tolerances(9, 4) = 2.60
    arrNW_Tolerances(10, 0) = 0.45: arrNW_Tolerances(10, 1) = 0.70: arrNW_Tolerances(10, 2) = 1.15: arrNW_Tolerances(10, 3) = 1.80: arrNW_Tolerances(10, 4) = 2.85
    arrNW_Tolerances(11, 0) = 0.49: arrNW_Tolerances(11, 1) = 0.78: arrNW_Tolerances(11, 2) = 1.25: arrNW_Tolerances(11, 3) = 2.00: arrNW_Tolerances(11, 4) = 3.15

    ' --- SILENT DEFAULTS (NO POP-UPS) ---
    Dim lngBaselineTG, lngMasterTG, iResetColor
    ' Default material selection = option "1"
    If dictMaterialMap.Exists("1") Then
        lngBaselineTG = dictMaterialMap("1")
    Else
        lngBaselineTG = 5 ' fallback
    End If

    ' Default master TG = baseline (which for material 1 is 5). Force TG=5 (per request).
    lngMasterTG = 5

    ' Default: reset processed dimensions to black
    iResetColor = vbYes

    ' --- MAIN PROCESSING LOOP ---
    Dim oSheets, oSheet, oViews, oView, oDims, oDim
    Dim dblTol, dblRoundedTol
    Dim iBlueCount, iDefaultCount, iGreenCount
    Dim oVisProps, lRed, lGreen, lBlue, arrCurrentTable
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

                            ' Defensive: try both text retrieval calls (some CATIA versions differ)
                            On Error Resume Next
                            Err.Clear
                            oDimValue.GetBuiltText 1, sBeforeText, sAfterText, sUpperText, sLowerText
                            If Err.Number <> 0 Then
                                Err.Clear
                                oDimValue.GetBaultText 1, sBeforeText, sAfterText, sUpperText, sLowerText
                            End If
                            On Error GoTo 0

                            ' Skip reference dimensions (parentheses)
                            If InStr(sBeforeText, "(") = 0 And InStr(sAfterText, ")") = 0 Then
                                ' Blue = Non-Tool-Specific (NW), default/other = Tool-Specific (TW)
                                If lRed = 0 And lGreen = 0 And lBlue = 255 Then
                                    arrCurrentTable = arrNW_Tolerances
                                    iBlueCount = iBlueCount + 1
                                Else
                                    arrCurrentTable = arrTW_Tolerances
                                    iDefaultCount = iDefaultCount + 1
                                End If

                                dblTol = GetToleranceValue(oDimValue.Value, lngMasterTG, arrNominalRanges, arrCurrentTable)
                                If dblTol > 0 Then
                                    dblRoundedTol = RoundToNearest05(dblTol)
                                    ' Apply symmetric tolerances
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

    ' Silent finish (no MsgBox)
End Sub

Private Function GetToleranceValue(ByVal dblNominal, ByVal lngTargetTG, ByRef arrRanges, ByRef arrTols)
    GetToleranceValue = 0
    Dim i, iRow, iCol
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
    iCol = lngTargetTG - 4
    If iRow > -1 And iCol >= 0 And iCol <= 4 Then
        GetToleranceValue = arrTols(iRow, iCol)
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
