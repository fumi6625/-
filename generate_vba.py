"""
VBAバイナリ生成スクリプト

LibreOffice UNO を使って検索マクロ入りの .xlsm テンプレートを生成し、
そこから vbaProject.bin を抽出します。

使い方: python generate_vba.py
出力: output/vba_project.bin
"""
import os
import sys
import time
import zipfile
import subprocess
import tempfile
import socket

# VBAマクロのソースコード
VBA_CODE = r'''
Option Explicit

' ===================================================
' 検索実行マクロ
' 「検索条件」シートの B1〜B4 を読み、
' 食べログ・ホットペッパーグルメ シートの行を絞り込む
' ===================================================
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

    genres    = Trim(wsSearch.Range("B1").Value)   ' ジャンル（部分一致）
    station   = Trim(wsSearch.Range("B2").Value)   ' 最寄駅（部分一致）
    budgetMax = CLng(0 & wsSearch.Range("B3").Value) ' 予算上限（0=フィルタなし）
    seatsMin  = CLng(0 & wsSearch.Range("B4").Value) ' 最低席数（0=フィルタなし）

    Dim sheetNames(1) As String
    sheetNames(0) = "食べログ"
    sheetNames(1) = "ホットペッパーグルメ"

    Dim s As Integer
    For s = 0 To 1
        On Error Resume Next
        Set wsData = ThisWorkbook.Sheets(sheetNames(s))
        On Error GoTo ErrHandler
        If wsData Is Nothing Then GoTo NextSheet

        lastRow = wsData.Cells(wsData.Rows.Count, 1).End(xlUp).Row
        If lastRow < 2 Then GoTo NextSheet

        ' オートフィルター解除して全行表示してからマクロフィルタ
        wsData.Rows("2:" & lastRow).Hidden = False

        For i = 2 To lastRow
            visible = True

            ' ジャンル（D列 = 4列目）
            If genres <> "" Then
                If InStr(1, wsData.Cells(i, 4).Value, genres, vbTextCompare) = 0 Then
                    visible = False
                End If
            End If

            ' 最寄駅（B列 = 2列目）
            If visible And station <> "" Then
                If InStr(1, wsData.Cells(i, 2).Value, station, vbTextCompare) = 0 Then
                    visible = False
                End If
            End If

            ' 予算上限（I列 = 9列目）
            If visible And budgetMax > 0 Then
                Dim bVal As Long
                bVal = CLng(0 & wsData.Cells(i, 9).Value)
                If bVal > budgetMax Then visible = False
            End If

            ' 最低席数（G列 = 7列目）
            If visible And seatsMin > 0 Then
                Dim sVal As Long
                sVal = CLng(0 & wsData.Cells(i, 7).Value)
                If sVal < seatsMin Then visible = False
            End If

            wsData.Rows(i).Hidden = Not visible
        Next i

NextSheet:
        Set wsData = Nothing
    Next s

    MsgBox "検索が完了しました。" & Chr(10) & _
           "条件に一致する行のみ表示されています。" & Chr(10) & _
           "リセットするには「検索リセット」ボタンを押してください。", _
           vbInformation, "検索完了"
    Exit Sub

ErrHandler:
    MsgBox "エラーが発生しました: " & Err.Description, vbCritical, "エラー"
End Sub

' ===================================================
' 検索リセットマクロ（全行を再表示）
' ===================================================
Sub ResetSearch()
    Dim wsData As Worksheet
    Dim lastRow As Long

    Dim sheetNames(1) As String
    sheetNames(0) = "食べログ"
    sheetNames(1) = "ホットペッパーグルメ"

    Dim s As Integer
    For s = 0 To 1
        On Error Resume Next
        Set wsData = ThisWorkbook.Sheets(sheetNames(s))
        On Error GoTo 0
        If Not wsData Is Nothing Then
            lastRow = wsData.Cells(wsData.Rows.Count, 1).End(xlUp).Row
            If lastRow >= 2 Then
                wsData.Rows("2:" & lastRow).Hidden = False
            End If
        End If
        Set wsData = Nothing
    Next s

    ' 検索条件をクリア
    With ThisWorkbook.Sheets("検索条件")
        .Range("B1").Value = ""
        .Range("B2").Value = ""
        .Range("B3").Value = 0
        .Range("B4").Value = 0
    End With

    MsgBox "検索条件をリセットし、全件表示しました。", vbInformation, "リセット完了"
End Sub
'''


def _wait_for_port(port: int, timeout: float = 20.0) -> bool:
    """LibreOffice サーバーが起動するまで待機"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("localhost", port), timeout=1):
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.5)
    return False


def _create_xlsm_with_uno(xlsm_path: str) -> bool:
    """LibreOffice UNO を使って xlsm を作成する"""
    port = 2002
    lo_proc = None
    try:
        # LibreOffice をサーバーモードで起動
        lo_proc = subprocess.Popen(
            [
                "libreoffice", "--headless", "--norestore", "--nofirststartwizard",
                f"--accept=socket,host=localhost,port={port};"
                "urp;StarOffice.ServiceManager",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if not _wait_for_port(port, timeout=30):
            print("LibreOffice サーバーの起動タイムアウト")
            return False

        # UNO ブリッジ経由で操作
        sys.path.insert(0, "/usr/lib/python3/dist-packages")
        import uno  # noqa: PLC0415
        from com.sun.star.beans import PropertyValue  # noqa: PLC0415

        localCtx = uno.getComponentContext()
        resolver = localCtx.ServiceManager.createInstanceWithContext(
            "com.sun.star.bridge.UnoUrlResolver", localCtx
        )
        ctx = resolver.resolve(
            f"uno:socket,host=localhost,port={port};"
            "urp;StarOffice.ComponentContext"
        )
        smgr = ctx.ServiceManager
        desktop = smgr.createInstanceWithContext(
            "com.sun.star.frame.Desktop", ctx
        )

        # 新規スプレッドシートを作成
        doc = desktop.loadComponentFromURL(
            "private:factory/scalc", "_blank", 0, ()
        )

        # Basic モジュールに VBA コードを追加
        basic_lib = doc.BasicLibraries
        basic_lib.createLibrary("Standard")
        lib = basic_lib.getByName("Standard")
        lib.insertByName("Module1", VBA_CODE)

        # xlsm として保存
        props = []
        p = PropertyValue()
        p.Name = "FilterName"
        p.Value = "Calc MS Excel 2007 XML"
        props.append(p)
        p2 = PropertyValue()
        p2.Name = "FilterFlags"
        p2.Value = 0x400  # VBA フラグ

        abs_path = os.path.abspath(xlsm_path)
        doc.storeToURL(f"file://{abs_path}", tuple(props))
        doc.close(True)
        return True

    except Exception as e:
        print(f"UNO エラー: {e}")
        return False
    finally:
        if lo_proc:
            lo_proc.terminate()
            lo_proc.wait(timeout=5)


def _create_xlsm_headless(xlsm_path: str) -> bool:
    """
    LibreOffice Python スクリプト経由で XLSM を作成する（フォールバック）。
    UNO が失敗した場合に使用。
    """
    script = f"""
import uno
from com.sun.star.beans import PropertyValue

ctx = uno.getComponentContext()
smgr = ctx.ServiceManager
desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)

doc = desktop.loadComponentFromURL("private:factory/scalc", "_blank", 0, ())

basic_lib = doc.BasicLibraries
basic_lib.createLibrary("Standard")
lib = basic_lib.getByName("Standard")
lib.insertByName("Module1", \"\"\"
{VBA_CODE.replace(chr(34), chr(34)*2)}
\"\"\")

props = []
p = PropertyValue()
p.Name = "FilterName"
p.Value = "Calc MS Excel 2007 XML"
props.append(p)

doc.storeToURL("file://{os.path.abspath(xlsm_path)}", tuple(props))
doc.close(True)
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        f.write(script)
        script_path = f.name

    try:
        result = subprocess.run(
            ["libreoffice", "--headless", "--norestore",
             "--nofirststartwizard",
             f"macro:///Standard.Scripts.Python.{script_path}"],
            timeout=30,
            capture_output=True,
        )
        return result.returncode == 0
    except Exception as e:
        print(f"ヘッドレス実行エラー: {e}")
        return False
    finally:
        os.unlink(script_path)


def extract_vba_bin(xlsm_path: str, out_path: str) -> bool:
    """xlsm ファイルから vbaProject.bin を抽出する"""
    try:
        with zipfile.ZipFile(xlsm_path, "r") as z:
            names = z.namelist()
            vba_entry = next(
                (n for n in names if n.lower().endswith("vbaproject.bin")),
                None,
            )
            if not vba_entry:
                print(f"vbaProject.bin が見つかりません: {names}")
                return False
            data = z.read(vba_entry)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(data)
        print(f"vbaProject.bin を抽出しました → {out_path} ({len(data)} bytes)")
        return True
    except Exception as e:
        print(f"抽出エラー: {e}")
        return False


def main():
    os.makedirs("output", exist_ok=True)
    out_bin = "output/vba_project.bin"

    if os.path.exists(out_bin):
        print(f"既存の {out_bin} を使用します。再生成するにはファイルを削除してください。")
        return

    with tempfile.NamedTemporaryFile(
        suffix=".xlsm", delete=False
    ) as tmp:
        tmp_xlsm = tmp.name

    print("LibreOffice で XLSM テンプレートを生成中...")
    success = _create_xlsm_with_uno(tmp_xlsm)

    if success and os.path.exists(tmp_xlsm):
        success = extract_vba_bin(tmp_xlsm, out_bin)
    else:
        print("UNO による生成に失敗しました。フォールバックを試みます...")
        success = _create_xlsm_headless(tmp_xlsm)
        if success and os.path.exists(tmp_xlsm):
            success = extract_vba_bin(tmp_xlsm, out_bin)

    try:
        os.unlink(tmp_xlsm)
    except OSError:
        pass

    if success:
        print("VBAバイナリの生成が完了しました。")
    else:
        print(
            "VBAバイナリの自動生成に失敗しました。\n"
            "Windowsの Excel で xlsm ファイルを作成し、\n"
            "以下のコマンドで vbaProject.bin を抽出してください:\n"
            "  python -m xlsxwriter.utility extract_vba your_file.xlsm output/vba_project.bin\n"
            "\n通常の xlsx（VBAなし・オートフィルター付き）で出力します。"
        )


if __name__ == "__main__":
    main()
