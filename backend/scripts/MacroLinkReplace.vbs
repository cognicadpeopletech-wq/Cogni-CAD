' Link2DWith3D_Persistent.vbs

' Attempts robust linking while preserving already-open drawing (no "reopen" prompt).

' - Does not close or reopen the drawing if it's already open.

' - Tries several Add() API variants to create an associative view.

' - Leaves documents open (does not close them) if view creation fails.

' - Quiet mode (only one short final message). Remove final MsgBox for fully silent runs.



Option Explicit



' --- Configure these paths ---

Dim folder2D, folder3D

folder2D = "C:\Users\BAbhilash\Downloads\New folder\CATIA 3D & 2D standard files"

folder3D = "C:\Users\BAbhilash\Downloads\New folder"



Dim fso

Set fso = CreateObject("Scripting.FileSystemObject")

If Not fso.FolderExists(folder2D) Then

    MsgBox "2D folder not found: " & folder2D, vbCritical, "Folder not found"

    WScript.Quit

End If

If Not fso.FolderExists(folder3D) Then

    MsgBox "3D folder not found: " & folder3D, vbCritical, "Folder not found"

    WScript.Quit

End If



' --- Manual mapping: DrawingBaseName -> 3DBaseName (without extension) ---

Dim nameMap

Set nameMap = CreateObject("Scripting.Dictionary")

nameMap.Add "Drawing2", "Mechanical gear"    ' <-- add mapping(s) here



' --- Get CATIA instance ---

Dim CATIA

On Error Resume Next

Set CATIA = GetObject(, "CATIA.Application")

On Error GoTo 0



If CATIA Is Nothing Then

    MsgBox "CATIA is not running. Please start CATIA and retry.", vbExclamation, "CATIA not running"

    WScript.Quit

End If



Dim folder, files, file2D

Set folder = fso.GetFolder(folder2D)

Set files = folder.Files



Dim successCount, failCount

successCount = 0

failCount = 0



For Each file2D In files

    If LCase(fso.GetExtensionName(file2D.Name)) = "catdrawing" Then

        On Error Resume Next



        Dim drawBase, modelBase, modelPath

        drawBase = fso.GetBaseName(file2D.Name)



        ' Use mapping if present

        If nameMap.Exists(drawBase) Then

            modelBase = nameMap(drawBase)

        Else

            modelBase = drawBase

        End If



        ' Try exact .CATPart / .CATProduct

        modelPath = folder3D & "\" & modelBase & ".CATPart"

        If Not fso.FileExists(modelPath) Then

            modelPath = folder3D & "\" & modelBase & ".CATProduct"

        End If



        ' Flexible fallback: find any 3D file whose base name contains the drawing base name

        If Not fso.FileExists(modelPath) Then

            Dim f

            modelPath = ""

            For Each f In fso.GetFolder(folder3D).Files

                Dim ext, candBase

                ext = LCase(fso.GetExtensionName(f.Path))

                If ext = "catpart" Or ext = "catproduct" Then

                    candBase = LCase(fso.GetBaseName(f.Path))

                    If InStr(1, candBase, LCase(drawBase), vbTextCompare) > 0 Then

                        modelPath = f.Path

                        Exit For

                    End If

                End If

            Next

        End If



        If modelPath = "" Then

            ' no model found; count as failure and continue (no popup)

            failCount = failCount + 1

        Else

            ' --- Obtain drawingDoc without prompting (use open doc if present) ---

            Dim drawingDoc, modelDoc

            Set drawingDoc = Nothing

            Set modelDoc = Nothing



            Dim d

            For Each d In CATIA.Documents

                If LCase(d.Name) = LCase(fso.GetFileName(file2D.Path)) Then

                    Set drawingDoc = d

                    Exit For

                End If

            Next



            If drawingDoc Is Nothing Then

                ' Not open -> open it silently

                On Error Resume Next

                Set drawingDoc = CATIA.Documents.Open(file2D.Path)

                On Error GoTo 0

            End If



            ' --- Obtain modelDoc same way ---

            Dim m

            For Each m In CATIA.Documents

                If LCase(m.Name) = LCase(fso.GetFileName(modelPath)) Then

                    Set modelDoc = m

                    Exit For

                End If

            Next



            If modelDoc Is Nothing Then

                On Error Resume Next

                Set modelDoc = CATIA.Documents.Open(modelPath)

                On Error GoTo 0

            End If



            If drawingDoc Is Nothing Or modelDoc Is Nothing Then

                failCount = failCount + 1

            Else

                ' Activate the drawing window to help some CATIA versions accept view creation

                On Error Resume Next

                drawingDoc.Activate

                On Error GoTo 0



                ' --- Try multiple ways to create an associative view ---

                Dim sheet, views, newView

                Set newView = Nothing

                On Error Resume Next

                Set sheet = drawingDoc.Sheets.Item(1)

                On Error GoTo 0



                If Not sheet Is Nothing Then

                    Set views = sheet.Views



                    ' Strategy: try several variants, stop at first that returns an object

                    ' 1) If modelDoc is a Part doc, try views.Add(modelDoc.Part)

                    If LCase(fso.GetExtensionName(modelDoc.Name)) = "catpart" Then

                        On Error Resume Next

                        Set newView = views.Add(modelDoc.Part)

                        On Error GoTo 0

                    End If



                    ' 2) Try direct Add with the Document object

                    If newView Is Nothing Then

                        On Error Resume Next

                        Set newView = views.Add(modelDoc)

                        On Error GoTo 0

                    End If



                    ' 3) Try AddFromReference (some V5 versions)

                    If newView Is Nothing Then

                        On Error Resume Next

                        Set newView = views.AddFromReference(modelDoc)

                        On Error GoTo 0

                    End If



                    ' 4) Try to add using the object's product if product document

                    If newView Is Nothing Then

                        On Error Resume Next

                        If LCase(fso.GetExtensionName(modelDoc.Name)) = "catproduct" Then

                            ' attempt to use product reference

                            Set newView = views.Add(modelDoc.Product)

                        End If

                        On Error GoTo 0

                    End If



                    ' 5) Final fallback: try to create a projection view using the drawing view factory (best-effort)

                    If newView Is Nothing Then

                        On Error Resume Next

                        ' Some CATIA setups expose a DrawingViewFactory via sheet (not in all versions).

                        ' This will be best-effort and may silently fail if API not present.

                        Dim factory

                        Set factory = Nothing

                        On Error Resume Next

                        Set factory = drawingDoc.Sheets.Item(1).GetViewCreationFactory

                        On Error GoTo 0

                        If Not factory Is Nothing Then

                            On Error Resume Next

                            Set newView = factory.CreateViewFromDocument(modelDoc) ' hypothetical; may not exist

                            On Error GoTo 0

                        End If

                    End If



                    ' If view created, place/scale it; else leave open for manual linking

                    If Not newView Is Nothing Then

                        On Error Resume Next

                        newView.Scale = 0.6

                        newView.X = 100

                        newView.Y = 150

                        On Error GoTo 0

                        successCount = successCount + 1

                    Else

                        ' Still failed -> leave docs open so you can use Insert->Views manually

                        failCount = failCount + 1

                    End If

                Else

                    ' No sheet 1 found

                    failCount = failCount + 1

                End If

            End If

        End If



        On Error GoTo 0

    End If

Next



' Final short status - remove or comment out MsgBox if you want absolutely silent run

MsgBox "Linking finished. Success: " & successCount & "  Fail/Manual: " & failCount, vbInformation, "Done"

