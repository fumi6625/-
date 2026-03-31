"""
ODS経由での vbaProject.bin 生成スクリプト

1. LibreOffice Basic マクロ付きの ODS ファイルを zipfile で作成
2. LibreOffice --convert-to でXLSM変換
3. XLSM から vbaProject.bin を抽出
"""
import os
import zipfile
import subprocess
import tempfile
import time

# VBAコード（LibreOffice Basic として記述）
LO_BASIC_CODE = r'''
Option Explicit

Sub SearchRestaurants()
    Dim wsSearch As Object
    Dim wsData   As Object
    Dim oDoc     As Object
    Dim genres   As String
    Dim station  As String
    Dim budgetMax As Long
    Dim seatsMin  As Long
    Dim lastRow As Long
    Dim i As Long
    Dim visible As Boolean

    oDoc = ThisComponent
    wsSearch = oDoc.Sheets.getByName("検索条件")

    genres    = Trim(wsSearch.getCellByPosition(1, 3).getString())
    station   = Trim(wsSearch.getCellByPosition(1, 4).getString())
    budgetMax = CLng(wsSearch.getCellByPosition(1, 5).getValue())
    seatsMin  = CLng(wsSearch.getCellByPosition(1, 6).getValue())

    Dim sheetNames(1) As String
    sheetNames(0) = "食べログ"
    sheetNames(1) = "ホットペッパーグルメ"

    Dim s As Integer
    For s = 0 To 1
        If Not oDoc.Sheets.hasByName(sheetNames(s)) Then GoTo NextSheet
        wsData = oDoc.Sheets.getByName(sheetNames(s))
        lastRow = wsData.getCellByPosition(0, wsData.Rows.Count - 1).getCellAddress().Row

        ' Find actual last row
        Dim cursor As Object
        cursor = wsData.createCursor()
        cursor.gotoEndOfUsedArea(True)
        lastRow = cursor.getRangeAddress().EndRow

        For i = 1 To lastRow
            visible = True
            Dim genreVal As String: genreVal = wsData.getCellByPosition(3, i).getString()
            Dim stationVal As String: stationVal = wsData.getCellByPosition(1, i).getString()
            Dim budgetVal As Long: budgetVal = CLng(wsData.getCellByPosition(8, i).getValue())
            Dim seatsVal As Long: seatsVal = CLng(wsData.getCellByPosition(6, i).getValue())

            If genres <> "" And InStr(1, genreVal, genres, 1) = 0 Then visible = False
            If visible And station <> "" And InStr(1, stationVal, station, 1) = 0 Then visible = False
            If visible And budgetMax > 0 And budgetVal > budgetMax Then visible = False
            If visible And seatsMin > 0 And seatsVal < seatsMin Then visible = False

            Dim oRows As Object
            oRows = wsData.getRows()
            Dim oRow As Object
            oRow = oRows.getByIndex(i)
            oRow.IsVisible = visible
        Next i
NextSheet:
    Next s

    MsgBox "検索完了", 64, "検索"
End Sub

Sub ResetSearch()
    Dim oDoc As Object
    Dim wsData As Object
    oDoc = ThisComponent

    Dim sheetNames(1) As String
    sheetNames(0) = "食べログ"
    sheetNames(1) = "ホットペッパーグルメ"

    Dim s As Integer
    For s = 0 To 1
        If oDoc.Sheets.hasByName(sheetNames(s)) Then
            wsData = oDoc.Sheets.getByName(sheetNames(s))
            Dim cursor As Object
            cursor = wsData.createCursor()
            cursor.gotoEndOfUsedArea(True)
            Dim lastRow As Long
            lastRow = cursor.getRangeAddress().EndRow
            Dim i As Long
            For i = 1 To lastRow
                wsData.getRows().getByIndex(i).IsVisible = True
            Next i
        End If
    Next s

    If oDoc.Sheets.hasByName("検索条件") Then
        Dim ws As Object
        ws = oDoc.Sheets.getByName("検索条件")
        ws.getCellByPosition(1, 3).setString("")
        ws.getCellByPosition(1, 4).setString("")
        ws.getCellByPosition(1, 5).setValue(0)
        ws.getCellByPosition(1, 6).setValue(0)
    End If

    MsgBox "リセット完了", 64, "リセット"
End Sub
'''

# ODS マニフェスト
MANIFEST_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0">
 <manifest:file-entry manifest:media-type="application/vnd.oasis.opendocument.spreadsheet" manifest:full-path="/"/>
 <manifest:file-entry manifest:media-type="text/xml" manifest:full-path="content.xml"/>
 <manifest:file-entry manifest:media-type="text/xml" manifest:full-path="meta.xml"/>
 <manifest:file-entry manifest:media-type="text/xml" manifest:full-path="settings.xml"/>
 <manifest:file-entry manifest:media-type="text/xml" manifest:full-path="styles.xml"/>
 <manifest:file-entry manifest:media-type="" manifest:full-path="Basic/"/>
 <manifest:file-entry manifest:media-type="" manifest:full-path="Basic/Standard/"/>
 <manifest:file-entry manifest:media-type="text/xml" manifest:full-path="Basic/Standard/Module1.xml"/>
 <manifest:file-entry manifest:media-type="text/xml" manifest:full-path="Basic/Standard/script-lc.xml"/>
 <manifest:file-entry manifest:media-type="text/xml" manifest:full-path="Basic/script-lc.xml"/>
</manifest:manifest>'''

CONTENT_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<office:document-content
  xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
  xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
  xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
  office:version="1.3">
 <office:scripts/>
 <office:body>
  <office:spreadsheet>
   <table:table table:name="Sheet1">
    <table:table-row>
     <table:table-cell><text:p>dummy</text:p></table:table-cell>
    </table:table-row>
   </table:table>
  </office:spreadsheet>
 </office:body>
</office:document-content>'''

META_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<office:document-meta xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
  office:version="1.3">
 <office:meta/>
</office:document-meta>'''

STYLES_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<office:document-styles xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
  office:version="1.3">
 <office:styles/>
</office:document-styles>'''

SETTINGS_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<office:document-settings xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
  office:version="1.3">
 <office:settings/>
</office:document-settings>'''

BASIC_SCRIPT_LC = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE library:library PUBLIC "-//OpenOffice.org//DTD OfficeDocument 1.0//EN" "library.dtd">
<library:library xmlns:library="http://openoffice.org/2000/library"
  library:name="Standard" library:readonly="false" library:passwordprotected="false">
 <library:element library:name="Module1"/>
</library:library>'''

BASIC_MODULE_XML_TPL = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE script:module PUBLIC "-//OpenOffice.org//DTD OfficeDocument 1.0//EN" "module.dtd">
<script:module xmlns:script="http://openoffice.org/2000/script"
  script:name="Module1" script:language="StarBasic">{code}</script:module>'''

BASIC_SCRIPT_COLLECTION_LC = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE library:libraries PUBLIC "-//OpenOffice.org//DTD OfficeDocument 1.0//EN" "libraries.dtd">
<library:libraries xmlns:library="http://openoffice.org/2000/library"
  xmlns:xlink="http://www.w3.org/1999/xlink">
 <library:library library:name="Standard"
   xlink:href="Basic/Standard/script-lc.xml"
   xlink:type="simple" library:link="false"/>
</library:libraries>'''


def create_ods_with_macro(ods_path: str) -> None:
    """LibreOffice Basic マクロ入りの ODS ファイルを作成"""
    import xml.sax.saxutils as saxutils
    module_xml = BASIC_MODULE_XML_TPL.format(
        code=saxutils.escape(LO_BASIC_CODE)
    )

    with zipfile.ZipFile(ods_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("mimetype", "application/vnd.oasis.opendocument.spreadsheet",
                   compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/manifest.xml", MANIFEST_XML)
        z.writestr("content.xml", CONTENT_XML)
        z.writestr("meta.xml", META_XML)
        z.writestr("styles.xml", STYLES_XML)
        z.writestr("settings.xml", SETTINGS_XML)
        z.writestr("Basic/script-lc.xml", BASIC_SCRIPT_COLLECTION_LC)
        z.writestr("Basic/Standard/script-lc.xml", BASIC_SCRIPT_LC)
        z.writestr("Basic/Standard/Module1.xml", module_xml)


def convert_ods_to_xlsm(ods_path: str, out_dir: str) -> str | None:
    """LibreOffice でODSをXLSMに変換"""
    try:
        result = subprocess.run(
            [
                "libreoffice", "--headless", "--norestore",
                "--nofirststartwizard",
                "--convert-to", "xlsm",
                "--outdir", out_dir,
                ods_path,
            ],
            capture_output=True, text=True, timeout=60
        )
        print(result.stdout)
        if result.returncode != 0:
            print(f"LibreOffice エラー: {result.stderr}")
            return None

        base = os.path.splitext(os.path.basename(ods_path))[0]
        xlsm_path = os.path.join(out_dir, base + ".xlsm")
        if os.path.exists(xlsm_path):
            return xlsm_path
        # xlsxとして保存された場合もある
        xlsx_path = os.path.join(out_dir, base + ".xlsx")
        if os.path.exists(xlsx_path):
            return xlsx_path
        print(f"変換後ファイルが見つかりません: {out_dir}")
        return None
    except subprocess.TimeoutExpired:
        print("LibreOffice 変換タイムアウト")
        return None
    except Exception as e:
        print(f"変換エラー: {e}")
        return None


def extract_vba_bin(xlsm_path: str, out_path: str) -> bool:
    """XLSM から vbaProject.bin を抽出"""
    try:
        with zipfile.ZipFile(xlsm_path, "r") as z:
            names = z.namelist()
            vba_entry = next(
                (n for n in names if "vbaproject" in n.lower()),
                None,
            )
            if not vba_entry:
                print(f"vbaProject.bin が見つかりません。ファイル内容: {names[:10]}")
                return False
            data = z.read(vba_entry)

        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(data)
        print(f"✓ vbaProject.bin を抽出しました → {out_path} ({len(data):,} bytes)")
        return True
    except Exception as e:
        print(f"抽出エラー: {e}")
        return False


def main():
    os.makedirs("output", exist_ok=True)
    out_bin = "output/vba_project.bin"

    if os.path.exists(out_bin):
        print(f"既存の {out_bin} を使用します（再生成するにはファイルを削除）。")
        return True

    with tempfile.TemporaryDirectory() as tmpdir:
        ods_path = os.path.join(tmpdir, "macro_template.ods")
        print("ODS テンプレートを作成中...")
        create_ods_with_macro(ods_path)

        print("LibreOffice で XLSM に変換中...")
        xlsm_path = convert_ods_to_xlsm(ods_path, tmpdir)

        if not xlsm_path:
            print("XLSM 変換に失敗しました。")
            return False

        print(f"変換完了: {xlsm_path}")
        return extract_vba_bin(xlsm_path, out_bin)


if __name__ == "__main__":
    success = main()
    if not success:
        print(
            "\n自動生成に失敗しました。\n"
            "Windows の Excel で以下の手順で vba_project.bin を作成してください:\n"
            "1. Excel で新規ファイルを .xlsm として保存\n"
            "2. Alt+F11 → 挿入 → 標準モジュール → VBAコードを貼り付けて保存\n"
            "3. python -m xlsxwriter.utility extract_vba your_file.xlsm output/vba_project.bin"
        )
