Attribute VB_Name = "SearchModule"
'=================================================================
' 大阪レストラン検索マクロ
'
' 【インポート方法】
'  1. Excel で restaurants.xlsx を開き、名前を restaurants.xlsm に変更して保存
'  2. Alt+F11 でVBAエディタを開く
'  3. ファイル → ファイルのインポート → この vba_macro.bas を選択
'  4. 「検索条件」シートの上部にボタンを追加してマクロを割り当てる
'     (挿入 → 図形 → 四角形を描画 → 右クリック → マクロの割り当て)
'=================================================================
Option Explicit

'=================================================================
' 検索実行マクロ
' 「検索条件」シートの B4〜B7 を読み、
' 食べログ・ホットペッパーグルメ シートの行を絞り込む
'=================================================================
Sub SearchRestaurants()
    Dim wsSearch As Worksheet
    Dim wsData   As Worksheet
    Dim genres   As String
    Dim station  As String
    Dim budgetMax As Long
    Dim seatsMin  As Long
    Dim lastRow As Long
    Dim i As Long
    Dim visible As Boolean

    On Error GoTo ErrHandler

    Set wsSearch = ThisWorkbook.Sheets("検索条件")

    genres    = Trim(wsSearch.Range("B4").Value)             ' ジャンル（部分一致）
    station   = Trim(wsSearch.Range("B5").Value)             ' 最寄駅（部分一致）
    budgetMax = CLng(0 & wsSearch.Range("B6").Value)         ' 予算上限（0=フィルタなし）
    seatsMin  = CLng(0 & wsSearch.Range("B7").Value)         ' 最低席数（0=フィルタなし）

    Dim sheetNames(1) As String
    sheetNames(0) = "食べログ"
    sheetNames(1) = "ホットペッパーグルメ"

    Dim foundCount As Long
    foundCount = 0

    Dim s As Integer
    For s = 0 To 1
        On Error Resume Next
        Set wsData = Nothing
        Set wsData = ThisWorkbook.Sheets(sheetNames(s))
        On Error GoTo ErrHandler
        If wsData Is Nothing Then GoTo NextSheet

        lastRow = wsData.Cells(wsData.Rows.Count, 1).End(xlUp).Row
        If lastRow < 2 Then GoTo NextSheet

        ' まず全行表示
        wsData.Rows("2:" & lastRow).Hidden = False

        For i = 2 To lastRow
            visible = True

            ' ジャンル（D列 = 4列目）: 部分一致
            If genres <> "" Then
                If InStr(1, wsData.Cells(i, 4).Value, genres, vbTextCompare) = 0 Then
                    visible = False
                End If
            End If

            ' 最寄駅（B列 = 2列目）: 部分一致
            If visible And station <> "" Then
                If InStr(1, wsData.Cells(i, 2).Value, station, vbTextCompare) = 0 Then
                    visible = False
                End If
            End If

            ' 予算上限（I列 = 9列目）
            If visible And budgetMax > 0 Then
                Dim bStr As String
                bStr = wsData.Cells(i, 9).Value
                If bStr <> "" Then
                    Dim bVal As Long
                    bVal = CLng(bStr)
                    If bVal > budgetMax Then visible = False
                End If
            End If

            ' 最低席数（G列 = 7列目）
            If visible And seatsMin > 0 Then
                Dim sStr As String
                sStr = wsData.Cells(i, 7).Value
                If sStr <> "" Then
                    Dim sVal As Long
                    sVal = CLng(sStr)
                    If sVal < seatsMin Then visible = False
                End If
            End If

            wsData.Rows(i).Hidden = Not visible
            If visible Then foundCount = foundCount + 1
        Next i

NextSheet:
    Next s

    Dim msg As String
    msg = "検索が完了しました。" & Chr(10) & Chr(10) & _
          "件数: " & foundCount & " 件" & Chr(10) & Chr(10)

    If genres <> "" Then msg = msg & "ジャンル: " & genres & Chr(10)
    If station <> "" Then msg = msg & "最寄駅: " & station & Chr(10)
    If budgetMax > 0 Then msg = msg & "予算上限: " & Format(budgetMax, "#,##0") & "円" & Chr(10)
    If seatsMin > 0 Then msg = msg & "最低席数: " & seatsMin & "席" & Chr(10)

    msg = msg & Chr(10) & "リセットするには「検索リセット」ボタンを押してください。"
    MsgBox msg, vbInformation, "検索完了"
    Exit Sub

ErrHandler:
    MsgBox "エラーが発生しました: " & Err.Description, vbCritical, "エラー"
End Sub

'=================================================================
' 検索リセットマクロ（全行を再表示・検索条件をクリア）
'=================================================================
Sub ResetSearch()
    Dim wsData As Worksheet
    Dim lastRow As Long

    Dim sheetNames(1) As String
    sheetNames(0) = "食べログ"
    sheetNames(1) = "ホットペッパーグルメ"

    Dim s As Integer
    For s = 0 To 1
        On Error Resume Next
        Set wsData = Nothing
        Set wsData = ThisWorkbook.Sheets(sheetNames(s))
        On Error GoTo 0
        If Not wsData Is Nothing Then
            lastRow = wsData.Cells(wsData.Rows.Count, 1).End(xlUp).Row
            If lastRow >= 2 Then
                wsData.Rows("2:" & lastRow).Hidden = False
            End If
        End If
    Next s

    ' 検索条件をクリア
    On Error Resume Next
    With ThisWorkbook.Sheets("検索条件")
        .Range("B4").Value = ""
        .Range("B5").Value = ""
        .Range("B6").Value = 0
        .Range("B7").Value = 0
    End With
    On Error GoTo 0

    MsgBox "検索条件をリセットし、全件表示しました。", vbInformation, "リセット完了"
End Sub
