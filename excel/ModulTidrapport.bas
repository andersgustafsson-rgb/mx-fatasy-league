Attribute VB_Name = "ModulTidrapport"
Option Explicit

' Kopiera till Alt+F11 → Infoga modul (eller importera denna .bas).
' Spara arbetsboken som .xlsm. Alt+F8 → FlyttaTillValdManad (eller knapp).
' Efter flytt uppdateras «Diagram_timmar» + «Graf_timmar» automatiskt.
' Om du bara vill bygga om diagram från redan ifylld månadsflik: UppdateraSammanstallningOchDiagram.

Private Const COL_LAST As Long = 16
Private Const HDR_DEFAULT_KLISTRA As Long = 8
Private Const SHEET_DIAGRAM As String = "Diagram_timmar"
Private Const SHEET_CHART As String = "Graf_timmar"
Private Const SHEET_KLISTRA As String = "Klistra_in"

Public Sub FlyttaTillValdManad()
    Dim wsK As Worksheet
    Dim wsM As Worksheet
    Dim mName As String
    Dim hdrRow As Long
    Dim lastR As Long
    Dim r As Long
    Dim c As Long
    Dim rng As Range
    Dim hdr As Variant

    On Error GoTo EH

    Set wsK = Worksheets(SHEET_KLISTRA)

    mName = Trim$(CStr(wsK.Range("B1").Value))
    If Len(mName) = 0 Then
        MsgBox "Välj månad i cell B1 (listrutan) först.", vbExclamation, "Tidrapport"
        Exit Sub
    End If

    On Error Resume Next
    Set wsM = Worksheets(mName)
    On Error GoTo EH
    If wsM Is Nothing Then
        MsgBox "Det finns ingen flik som heter """ & mName & """.", vbExclamation, "Tidrapport"
        Exit Sub
    End If

    hdrRow = 0
    For r = 5 To 120
        If StrComp(Trim$(CStr(wsK.Cells(r, 1).Value)), "Namn", vbTextCompare) = 0 Then
            hdrRow = r
            Exit For
        End If
    Next r
    If hdrRow = 0 Then hdrRow = HDR_DEFAULT_KLISTRA

    lastR = wsK.Cells(wsK.Rows.Count, 1).End(xlUp).Row
    If lastR <= hdrRow Then
        MsgBox "Inga datarader under rubriken. Klistra in tabellen först.", vbInformation, "Tidrapport"
        Exit Sub
    End If

    Set rng = wsK.Range(wsK.Cells(hdrRow, 1), wsK.Cells(lastR, COL_LAST))

    Application.ScreenUpdating = False
    wsM.Cells.Clear
    rng.Copy Destination:=wsM.Range("A1")
    Application.CutCopyMode = False

    If lastR > hdrRow Then
        wsK.Range(wsK.Cells(hdrRow + 1, 1), wsK.Cells(lastR, COL_LAST)).ClearContents
    End If

    hdr = Split("Namn;Datum;Kl Fom;Kl Tom;Kl rast;Rast;Typ;Orsak;Bemanningstyp;Proc;Organisation;Kto;Tst;Bev;Bvä;Med", ";")
    For c = 1 To COL_LAST
        With wsK.Cells(HDR_DEFAULT_KLISTRA, c)
            .Value = hdr(c - 1)
            .Font.Bold = True
        End With
    Next c

    BuildDiagramAndChart wsM, mName

    Application.ScreenUpdating = True

    MsgBox "Klart: data på «" & mName & "», diagram uppdaterat på «" & SHEET_DIAGRAM & "» / «" & SHEET_CHART & "».", vbInformation, "Tidrapport"
    Exit Sub

EH:
    Application.ScreenUpdating = True
    MsgBox "Fel " & CStr(Err.Number) & ": " & Err.Description, vbCritical, "Tidrapport"
End Sub

' Läser månad från Klistra_in!B1 och bygger om tabell + diagram från den månadsfliken (ingen flytt).
Public Sub UppdateraSammanstallningOchDiagram()
    Dim wsK As Worksheet
    Dim wsM As Worksheet
    Dim mName As String

    On Error GoTo EH
    Set wsK = Worksheets(SHEET_KLISTRA)
    mName = Trim$(CStr(wsK.Range("B1").Value))
    If Len(mName) = 0 Then
        MsgBox "Välj månad i B1 på «" & SHEET_KLISTRA & "».", vbExclamation, "Tidrapport"
        Exit Sub
    End If
    On Error Resume Next
    Set wsM = Worksheets(mName)
    On Error GoTo EH
    If wsM Is Nothing Then
        MsgBox "Ingen flik """ & mName & """.", vbExclamation, "Tidrapport"
        Exit Sub
    End If

    Application.ScreenUpdating = False
    BuildDiagramAndChart wsM, mName
    Application.ScreenUpdating = True
    MsgBox "Diagram uppdaterat för «" & mName & "».", vbInformation, "Tidrapport"
    Exit Sub

EH:
    Application.ScreenUpdating = True
    MsgBox "Fel " & CStr(Err.Number) & ": " & Err.Description, vbCritical, "Tidrapport"
End Sub

' --- Intern: samma tim-/orsak-logik som scripts/feb_overtime_bar_charts.py ---

Private Sub BuildDiagramAndChart(wsData As Worksheet, ByVal fallbackMonthTab As String)
    Dim hdrData As Long
    Dim totals As Object
    Dim monthLabel As String
    Dim ordered As Variant
    Dim names() As String
    Dim nNames As Long
    Dim wsD As Worksheet
    Dim hdrRow As Long
    Dim sumCol As Long
    Dim lastRow As Long
    Dim i As Long
    Dim j As Long
    Dim r As Long
    Dim c As Long
    Dim nm As String
    Dim ors As String
    Dim gross As Double
    Dim net As Double
    Dim fom As Double
    Dim tom As Double
    Dim byOrs As Object
    Dim k As Variant
    Dim ok As Variant
    Dim rowSum As Double
    Dim v As Double
    Dim titleA As String

    hdrData = FindHeaderRowNamn(wsData)
    If hdrData = 0 Then Err.Raise vbObjectError + 1, , "Hittar ingen rad med «Namn» i kolumn A på datafliken."

    Set totals = AggregateTotals(wsData, hdrData)
    If totals.Count = 0 Then
        Err.Raise vbObjectError + 2, , _
            "Ingen timmar kunde räknas (rubrik på rad " & CStr(hdrData) & "). " & _
            "Kontrollera namn i kolumn A, tid i C/D (klockslag eller Excel-format), orsak i kolumn H."
    End If

    monthLabel = ParseMonthLabel(wsData, hdrData)
    If Len(monthLabel) = 0 Then monthLabel = fallbackMonthTab

    ordered = BuildOrderedColumns(totals)
    names = SortedNames(totals, ordered)
    nNames = UBound(names)

    Set wsD = GetOrCreateSheet(wsData.Parent, SHEET_DIAGRAM)
    wsD.Cells.Clear

    titleA = monthLabel & " — timmar per person (Tom − Fom, natt +24 h, rast «Rast» i min)"
    With wsD.Range("A1")
        .Value = titleA
        .Font.Bold = True
        .Font.Size = 12
    End With

    hdrRow = 3
    wsD.Cells(hdrRow, 1).Value = "Namn"
    wsD.Cells(hdrRow, 1).Font.Bold = True
    sumCol = 1 + UBound(ordered) + 1
    For i = 0 To UBound(ordered)
        wsD.Cells(hdrRow, 2 + i).Value = ordered(i)
        wsD.Cells(hdrRow, 2 + i).Font.Bold = True
    Next i
    wsD.Cells(hdrRow, sumCol).Value = "Summa h"
    wsD.Cells(hdrRow, sumCol).Font.Bold = True

    For i = 0 To nNames
        nm = names(i)
        r = hdrRow + 1 + i
        wsD.Cells(r, 1).Value = nm
        rowSum = 0#
        Set byOrs = totals(nm)
        For j = 0 To UBound(ordered)
            ors = CStr(ordered(j))
            If byOrs.Exists(ors) Then v = CDbl(byOrs(ors)) Else v = 0#
            v = Round(v, 2)
            wsD.Cells(r, 2 + j).Value = v
            rowSum = rowSum + v
        Next j
        wsD.Cells(r, sumCol).Value = Round(rowSum, 2)
    Next i

    lastRow = hdrRow + nNames + 1
    wsD.Columns("A").ColumnWidth = 34
    For c = 2 To sumCol
        wsD.Columns(c).ColumnWidth = 16
    Next c

    RecreateChartSheet wsData.Parent, wsD, hdrRow, lastRow, sumCol, monthLabel
End Sub

Private Function FindHeaderRowNamn(ws As Worksheet) As Long
    Dim r As Long
    Dim fallback As Long
    fallback = 0
    For r = 1 To 500
        If StrComp(Trim$(CStr(ws.Cells(r, 1).Value)), "Namn", vbTextCompare) <> 0 Then GoTo nxt
        If StrComp(Trim$(CStr(ws.Cells(r, 2).Value)), "Datum", vbTextCompare) = 0 Then
            FindHeaderRowNamn = r
            Exit Function
        End If
        If fallback = 0 Then fallback = r
nxt:
    Next r
    FindHeaderRowNamn = fallback
End Function

' Sista rad med innehåll i kolumn 1–16 (undviker att bara kolumn A ger fel xlUp när A är tom).
Private Function LastContentRowAfterHeader(ws As Worksheet, ByVal hdrRow As Long) As Long
    Dim c As Long
    Dim r As Long
    Dim m As Long
    m = hdrRow
    For c = 1 To COL_LAST
        r = ws.Cells(ws.Rows.Count, c).End(xlUp).Row
        If r > m Then m = r
    Next c
    LastContentRowAfterHeader = m
End Function

Private Function CleanStr(ByVal v As Variant) As String
    Dim s As String
    If IsError(v) Then CleanStr = "": Exit Function
    If IsNull(v) Or IsEmpty(v) Then CleanStr = "": Exit Function
    s = CStr(v)
    s = Replace(s, Chr$(160), " ")
    CleanStr = Trim$(s)
End Function

Private Function ParseTimeHrs(ByVal v As Variant) As Double
    Dim s As String
    Dim p As Long
    Dim h As Long
    Dim mi As Long
    Dim d As Double
    Dim dayFrac As Double

    ParseTimeHrs = -1#
    If IsError(v) Then Exit Function
    If IsEmpty(v) Or IsNull(v) Then Exit Function

    ' Excel lagrar ofta klockslag som datum/tal (seriedag + bråk av dygnet).
    If VarType(v) = vbDate Then
        ParseTimeHrs = Hour(CDate(v)) + Minute(CDate(v)) / 60# + Second(CDate(v)) / 3600#
        Exit Function
    End If
    If IsNumeric(v) And VarType(v) <> vbString Then
        d = CDbl(v)
        dayFrac = d - Fix(d)
        If dayFrac < 0# Then dayFrac = dayFrac + 1#
        ParseTimeHrs = dayFrac * 24#
        Exit Function
    End If

    s = CleanStr(v)
    If Len(s) = 0 Then Exit Function
    p = InStr(1, s, ":", vbBinaryCompare)
    If p <= 0 Then Exit Function
    On Error Resume Next
    h = CLng(Left$(s, p - 1))
    mi = CLng(Mid$(s, p + 1))
    On Error GoTo 0
    If mi < 0 Or mi > 59 Then Exit Function
    ParseTimeHrs = h + mi / 60#
End Function

Private Function ParseRastMinutes(ByVal v As Variant) As Double
    Dim s As String
    s = CleanStr(v)
    If Len(s) = 0 Then ParseRastMinutes = 0#: Exit Function
    s = Replace(s, ",", ".")
    On Error Resume Next
    ParseRastMinutes = CDbl(s)
    If Err.Number <> 0 Then ParseRastMinutes = 0#
    On Error GoTo 0
End Function

Private Function DurationHours(ByVal fom As Double, ByVal tom As Double) As Double
    Dim delta As Double
    delta = tom - fom
    If delta <= 0# Then delta = delta + 24#
    DurationHours = delta
End Function

Private Function NormalizeOrsak(ByVal raw As String) As String
    Dim r As String
    Dim low As String
    r = CleanStr(raw)
    If Len(r) = 0 Then NormalizeOrsak = "Övrigt": Exit Function
    low = LCase$(r)
    If InStr(1, low, "poäng inst", vbTextCompare) > 0 _
        Or InStr(1, low, "pong inst", vbTextCompare) > 0 _
        Or InStr(1, low, "kort ledig", vbTextCompare) > 0 Then
        NormalizeOrsak = OrsacAt(0): Exit Function
    End If
    If InStr(1, low, "stby", vbTextCompare) > 0 _
        Or InStr(1, low, "förskj", vbTextCompare) > 0 _
        Or InStr(1, low, "forskj", vbTextCompare) > 0 _
        Or InStr(1, low, "ater st", vbTextCompare) > 0 Then
        NormalizeOrsak = OrsacAt(1): Exit Function
    End If
    If InStr(1, low, "kontering", vbTextCompare) > 0 _
        Or InStr(1, low, "arbtid", vbTextCompare) > 0 Then
        NormalizeOrsak = OrsacAt(2): Exit Function
    End If
    If InStr(1, low, "stand by schema", vbTextCompare) > 0 _
        Or (InStr(1, low, "stand", vbTextCompare) > 0 And InStr(1, low, "schema", vbTextCompare) > 0) Then
        NormalizeOrsak = OrsacAt(3): Exit Function
    End If
    If InStr(1, low, "stand by ledig", vbTextCompare) > 0 _
        Or (InStr(1, low, "stand", vbTextCompare) > 0 And InStr(1, low, "ledig", vbTextCompare) > 0) Then
        NormalizeOrsak = OrsacAt(4): Exit Function
    End If
    NormalizeOrsak = r
End Function

Private Function OrsacAt(ByVal idx As Long) As String
    Dim a As Variant
    a = OrsacOrderArr()
    OrsacAt = CStr(a(idx))
End Function

Private Function OrsacOrderArr() As Variant
    OrsacOrderArr = Array( _
        "Poäng inst kort ledig", _
        "Poäng åter StBy/Förskj", _
        "Arbtid kontering", _
        "Stand by schema", _
        "Stand by ledig" _
    )
End Function

Private Function IsInOrsacOrder(ByVal s As String) As Boolean
    Dim a As Variant
    Dim i As Long
    a = OrsacOrderArr()
    For i = 0 To UBound(a)
        If StrComp(s, CStr(a(i)), vbTextCompare) = 0 Then IsInOrsacOrder = True: Exit Function
    Next i
    IsInOrsacOrder = False
End Function

Private Function AggregateTotals(ws As Worksheet, ByVal hdrRow As Long) As Object
    Dim totals As Object
    Dim r As Long
    Dim nm As String
    Dim fom As Double
    Dim tom As Double
    Dim rastM As Double
    Dim gross As Double
    Dim net As Double
    Dim ors As String
    Dim byOrs As Object

    Set totals = CreateObject("Scripting.Dictionary")
    On Error Resume Next
    totals.CompareMode = 1
    On Error GoTo 0

    Dim lastR As Long
    lastR = LastContentRowAfterHeader(ws, hdrRow)

    For r = hdrRow + 1 To lastR
        nm = CleanStr(ws.Cells(r, 1).Value)
        If Len(nm) = 0 Then GoTo nextR

        fom = ParseTimeHrs(ws.Cells(r, 3).Value)
        tom = ParseTimeHrs(ws.Cells(r, 4).Value)
        If fom < 0# Or tom < 0# Then GoTo nextR

        rastM = ParseRastMinutes(ws.Cells(r, 6).Value)
        gross = DurationHours(fom, tom)
        net = gross - rastM / 60#
        If net < 0# Then net = 0#

        ors = NormalizeOrsak(CleanStr(ws.Cells(r, 8).Value))

        If Not totals.Exists(nm) Then
            Set byOrs = CreateObject("Scripting.Dictionary")
            byOrs.CompareMode = 1
            totals.Add nm, byOrs
        End If
        Set byOrs = totals(nm)
        If Not byOrs.Exists(ors) Then byOrs.Add ors, 0#
        byOrs(ors) = CDbl(byOrs(ors)) + net
nextR:
    Next r

    Set AggregateTotals = totals
End Function

Private Function ParseMonthLabel(ws As Worksheet, ByVal hdrRow As Long) As String
    Dim r As Long
    Dim v As Variant
    Dim d As Date
    Dim s As String
    For r = hdrRow + 1 To hdrRow + 2000
        If r > ws.Rows.Count Then Exit For
        v = ws.Cells(r, 2).Value
        s = CleanStr(v)
        If Len(s) = 0 Then GoTo cont
        On Error Resume Next
        d = CDate(v)
        If Err.Number <> 0 Then
            Err.Clear
            d = CDate(Left$(s, 10))
        End If
        On Error GoTo 0
        If Year(d) > 1900 Then
            ParseMonthLabel = SweMonthName(Month(d)) & " " & CStr(Year(d))
            Exit Function
        End If
cont:
    Next r
    ParseMonthLabel = vbNullString
End Function

Private Function SweMonthName(ByVal m As Long) As String
    Select Case m
        Case 1: SweMonthName = "Januari"
        Case 2: SweMonthName = "Februari"
        Case 3: SweMonthName = "Mars"
        Case 4: SweMonthName = "April"
        Case 5: SweMonthName = "Maj"
        Case 6: SweMonthName = "Juni"
        Case 7: SweMonthName = "Juli"
        Case 8: SweMonthName = "Augusti"
        Case 9: SweMonthName = "September"
        Case 10: SweMonthName = "Oktober"
        Case 11: SweMonthName = "November"
        Case 12: SweMonthName = "December"
        Case Else: SweMonthName = ""
    End Select
End Function

Private Function BuildOrderedColumns(totals As Object) As Variant
    Dim base As Variant
    Dim extras() As String
    Dim nEx As Long
    Dim k As Variant
    Dim ok As Variant
    Dim byOrs As Object
    Dim s As String
    Dim i As Long
    Dim j As Long
    Dim out() As String
    Dim nOut As Long

    base = OrsacOrderArr()
    nEx = -1
    ReDim extras(0 To 0)

    For Each k In totals.Keys
        Set byOrs = totals(k)
        For Each ok In byOrs.Keys
            s = CStr(ok)
            If Not IsInOrsacOrder(s) Then
                If Not StringInSortedArray(extras, nEx, s) Then
                    nEx = nEx + 1
                    If nEx > UBound(extras) Then ReDim Preserve extras(0 To nEx + 8)
                    extras(nEx) = s
                End If
            End If
        Next ok
    Next k

    If nEx >= 0 Then SortStringArrayAsc extras, nEx

    nOut = UBound(base) + (nEx + 1)
    ReDim out(0 To nOut)
    For i = 0 To UBound(base)
        out(i) = CStr(base(i))
    Next i
    j = UBound(base) + 1
    For i = 0 To nEx
        out(j) = extras(i)
        j = j + 1
    Next i

    BuildOrderedColumns = out
End Function

Private Function StringInSortedArray(arr() As String, ByVal lastIdx As Long, ByVal s As String) As Boolean
    Dim i As Long
    For i = 0 To lastIdx
        If StrComp(arr(i), s, vbTextCompare) = 0 Then StringInSortedArray = True: Exit Function
    Next i
    StringInSortedArray = False
End Function

Private Sub SortStringArrayAsc(arr() As String, ByVal lastIdx As Long)
    Dim i As Long
    Dim j As Long
    Dim t As String
    For i = 0 To lastIdx - 1
        For j = i + 1 To lastIdx
            If StrComp(arr(i), arr(j), vbTextCompare) > 0 Then
                t = arr(i): arr(i) = arr(j): arr(j) = t
            End If
        Next j
    Next i
End Sub

Private Function SortedNames(totals As Object, ordered As Variant) As String()
    Dim keys() As String
    Dim sums() As Double
    Dim n As Long
    Dim k As Variant
    Dim byOrs As Object
    Dim ok As Variant
    Dim i As Long
    Dim j As Long
    Dim t As String
    Dim ts As Double

    n = totals.Count - 1
    If n < 0 Then
        ReDim keys(0 To -1)
        SortedNames = keys
        Exit Function
    End If

    ReDim keys(0 To n)
    ReDim sums(0 To n)
    i = 0
    For Each k In totals.Keys
        keys(i) = CStr(k)
        Set byOrs = totals(k)
        sums(i) = 0#
        For Each ok In byOrs.Keys
            sums(i) = sums(i) + CDbl(byOrs(ok))
        Next ok
        i = i + 1
    Next k

    For i = 0 To n - 1
        For j = i + 1 To n
            If sums(j) > sums(i) Or (sums(j) = sums(i) And StrComp(keys(j), keys(i), vbTextCompare) < 0) Then
                ts = sums(i): sums(i) = sums(j): sums(j) = ts
                t = keys(i): keys(i) = keys(j): keys(j) = t
            End If
        Next j
    Next i

    SortedNames = keys
End Function

Private Function GetOrCreateSheet(wb As Workbook, ByVal sheetName As String) As Worksheet
    Dim ws As Worksheet
    On Error Resume Next
    Set ws = wb.Worksheets(sheetName)
    On Error GoTo 0
    If ws Is Nothing Then
        Set ws = wb.Worksheets.Add(After:=wb.Worksheets(wb.Worksheets.Count))
        On Error Resume Next
        ws.Name = sheetName
        On Error GoTo 0
    End If
    Set GetOrCreateSheet = ws
End Function

Private Sub RecreateChartSheet(wb As Workbook, wsD As Worksheet, ByVal hdrRow As Long, ByVal lastRow As Long, ByVal sumCol As Long, ByVal monthLabel As String)
    Dim ch As Chart
    Dim rng As Range

    Application.DisplayAlerts = False
    On Error Resume Next
    wb.Charts(SHEET_CHART).Delete
    On Error GoTo 0
    Application.DisplayAlerts = True

    Set rng = wsD.Range(wsD.Cells(hdrRow, 1), wsD.Cells(lastRow, sumCol))
    Set ch = wb.Charts.Add
    ch.Name = SHEET_CHART
    ch.ChartType = xlBarStacked
    ch.SetSourceData Source:=rng, PlotBy:=xlRows
    ch.HasTitle = True
    ch.ChartTitle.Text = monthLabel & " — timmar per person (per status)"
    On Error Resume Next
    ch.Axes(xlValue).HasTitle = True
    ch.Axes(xlValue).AxisTitle.Text = "Timmar"
    On Error GoTo 0
    ch.Legend.Position = xlLegendPositionRight
End Sub
