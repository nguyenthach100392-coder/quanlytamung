# -*- coding: utf-8 -*-
"""Export du lieu tu SQLite ra file Excel theo dung mau tracker."""
import os
import io
import shutil
from datetime import datetime, date, timedelta
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.formatting.rule import FormulaRule, CellIsRule

from db import get_conn

THIN = Side(border_style="thin", color="999999")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
HEADER_FILL = PatternFill("solid", start_color="1F4E78")
YELLOW_FILL = PatternFill("solid", start_color="FFF2CC")
GREEN_FILL = PatternFill("solid", start_color="C6EFCE")
RED_FILL = PatternFill("solid", start_color="FFC7CE")
HEADER_FONT = Font(name="Arial", bold=True, color="FFFFFF", size=11)
BOLD = Font(name="Arial", bold=True, size=11)
NORMAL = Font(name="Arial", size=10)
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)
RIGHT = Alignment(horizontal="right", vertical="center")


def _style_header(ws, row, cols):
    for c in range(1, cols + 1):
        cell = ws.cell(row=row, column=c)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = CENTER
        cell.border = BORDER


def export_excel(output_path=None):
    """Build file Excel tu SQLite. Tra ve duong dan file."""
    conn = get_conn()
    wb = Workbook()

    # Sheet 1
    ws1 = wb.active
    ws1.title = "1.SoTamUng"
    h1 = ["Ma giai ngan","Khach hang","Don vi thu huong","Phong","So hop dong","Gia tri HD","So tien tam ung","% Tam ung",
          "Ngay giai ngan","Ngay ket thuc HD","Han bo sung HD cuoi","% Khau tru/dot",
          "Khau tru luy ke","HD da bo sung luy ke","Du can bo sung","% Hoan thanh","So ngay con lai","Trang thai","Ghi chu"]
    ws1.append(h1)
    _style_header(ws1, 1, len(h1))
    ws1.row_dimensions[1].height = 42
    for i,w in enumerate([16,22,22,12,15,16,16,11,14,14,16,13,16,16,16,13,13,16,22], 1):
        ws1.column_dimensions[get_column_letter(i)].width = w

    rows = conn.execute("SELECT * FROM tam_ung ORDER BY ngay_giai_ngan DESC").fetchall()
    today = date.today()
    for i, r in enumerate(rows, start=2):
        # Computed values
        kt_luy_ke = conn.execute(
            "SELECT COALESCE(SUM(kl_truoc_vat * ?),0) FROM hstt WHERE ma_giai_ngan=?",
            (r["pct_khau_tru"], r["ma_giai_ngan"])
        ).fetchone()[0]
        hd_luy_ke = conn.execute(
            "SELECT COALESCE(SUM(tien_truoc_vat),0) FROM hoa_don WHERE ma_giai_ngan=? AND status='approved'",
            (r["ma_giai_ngan"],)
        ).fetchone()[0]
        du = max(r["so_tien_tu"] - hd_luy_ke, 0)
        pct_done = hd_luy_ke / r["so_tien_tu"] if r["so_tien_tu"] else 0
        nkt = r["ngay_ket_thuc_hd"]
        han_cuoi = nkt - timedelta(days=30) if nkt else None
        ngay_con = (han_cuoi - today).days if han_cuoi else 0

        if hd_luy_ke >= r["so_tien_tu"]:
            trang_thai = "Hoan tat"
        elif han_cuoi and today > han_cuoi:
            trang_thai = "Qua han"
        elif ngay_con <= 15:
            trang_thai = "Sap den han"
        else:
            trang_thai = "Dang theo doi"

        vals = [
            r["ma_giai_ngan"], r["khach_hang"], r.get("don_vi_thu_huong") or "", r["phong_phu_trach"] or "", r["so_hd"] or "",
            r["gia_tri_hd"] or 0, r["so_tien_tu"],
            (r["so_tien_tu"]/r["gia_tri_hd"]) if r["gia_tri_hd"] else 0,
            r["ngay_giai_ngan"], nkt, han_cuoi, r["pct_khau_tru"],
            kt_luy_ke, hd_luy_ke, du, pct_done, ngay_con, trang_thai, r["ghi_chu"] or ""
        ]
        for c, v in enumerate(vals, start=1):
            cell = ws1.cell(row=i, column=c, value=v)
            cell.border = BORDER; cell.font = NORMAL
            cell.alignment = LEFT if c in (1,2,3,4,5,19) else CENTER
        # formats
        for c in (6,7,13,14,15): ws1.cell(row=i,column=c).number_format = "#,##0;(#,##0);-"
        for c in (8,12,16): ws1.cell(row=i,column=c).number_format = "0.0%"
        for c in (9,10,11): ws1.cell(row=i,column=c).number_format = "dd/mm/yyyy"
        ws1.cell(row=i,column=17).number_format = "0"

    if rows:
        lr = 1 + len(rows)
        ws1.conditional_formatting.add(f"R2:R{lr}", FormulaRule(formula=['$R2="Qua han"'], fill=RED_FILL, font=Font(bold=True,color="9C0006")))
        ws1.conditional_formatting.add(f"R2:R{lr}", FormulaRule(formula=['$R2="Sap den han"'], fill=YELLOW_FILL, font=Font(bold=True,color="9C5700")))
        ws1.conditional_formatting.add(f"R2:R{lr}", FormulaRule(formula=['$R2="Hoan tat"'], fill=GREEN_FILL, font=Font(bold=True,color="006100")))
    ws1.freeze_panes = "B2"

    # Sheet 2: HSTT
    ws2 = wb.create_sheet("2.HoSoThanhToanKL")
    h2 = ["Ma giai ngan","Dot #","Ngay HSTT","KL truoc VAT","% Khau tru","Khau tru TU dot",
          "HD bo sung tuong ung","Du cua dot","Han bo sung dot","Tinh trang","Ghi chu"]
    ws2.append(h2); _style_header(ws2,1,len(h2))
    for i,w in enumerate([16,8,14,18,11,18,18,16,16,14,22],1):
        ws2.column_dimensions[get_column_letter(i)].width = w

    hstt = conn.execute("""
        SELECT h.*, t.pct_khau_tru as pct FROM hstt h
        LEFT JOIN tam_ung t ON h.ma_giai_ngan = t.ma_giai_ngan
        ORDER BY h.ma_giai_ngan, h.dot_so
    """).fetchall()
    for i, r in enumerate(hstt, start=2):
        pct = r["pct"] or 0.1
        kt = r["kl_truoc_vat"] * pct
        hd_dot = conn.execute(
            "SELECT COALESCE(SUM(tien_truoc_vat),0) FROM hoa_don WHERE ma_giai_ngan=? AND dot_so=? AND status='approved'",
            (r["ma_giai_ngan"], r["dot_so"])
        ).fetchone()[0]
        du = max(kt - hd_dot, 0)
        han = r["ngay_hstt"] + timedelta(days=15) if r["ngay_hstt"] else None
        if hd_dot >= kt:
            tt = "Du HD"
        elif han and today > han:
            tt = "Tre han"
        else:
            tt = "Dang cho HD"
        vals = [r["ma_giai_ngan"], r["dot_so"], r["ngay_hstt"], r["kl_truoc_vat"], pct, kt, hd_dot, du, han, tt, r["ghi_chu"] or ""]
        for c, v in enumerate(vals, start=1):
            cell = ws2.cell(row=i, column=c, value=v)
            cell.border = BORDER; cell.font = NORMAL
            cell.alignment = LEFT if c == 11 else CENTER
        ws2.cell(row=i,column=3).number_format = "dd/mm/yyyy"
        ws2.cell(row=i,column=9).number_format = "dd/mm/yyyy"
        for c in (4,6,7,8): ws2.cell(row=i,column=c).number_format = "#,##0;(#,##0);-"
        ws2.cell(row=i,column=5).number_format = "0.0%"

    if hstt:
        lr = 1 + len(hstt)
        ws2.conditional_formatting.add(f"J2:J{lr}", FormulaRule(formula=['$J2="Tre han"'], fill=RED_FILL, font=Font(bold=True,color="9C0006")))
        ws2.conditional_formatting.add(f"J2:J{lr}", FormulaRule(formula=['$J2="Dang cho HD"'], fill=YELLOW_FILL, font=Font(bold=True,color="9C5700")))
        ws2.conditional_formatting.add(f"J2:J{lr}", FormulaRule(formula=['$J2="Du HD"'], fill=GREEN_FILL, font=Font(bold=True,color="006100")))
    ws2.freeze_panes = "B2"

    # Sheet 3: HD bo sung
    ws3 = wb.create_sheet("3.HoaDonBoSung")
    h3 = ["STT","Ma giai ngan","Dot #","Ngay HD","So HD","MST ban","Ten ban","Tien truoc VAT","VAT","Tong","Status","Upload boi","Ngay upload","Ghi chu"]
    ws3.append(h3); _style_header(ws3,1,len(h3))
    for i,w in enumerate([6,16,8,12,14,14,28,16,14,16,11,14,14,20],1):
        ws3.column_dimensions[get_column_letter(i)].width = w
    hd = conn.execute("SELECT * FROM hoa_don ORDER BY ma_giai_ngan, dot_so, ngay_hd").fetchall()
    for i, r in enumerate(hd, start=2):
        vals = [i-1, r["ma_giai_ngan"], r["dot_so"], r["ngay_hd"], r["so_hd"], r["mst_ban"] or "",
                r["ten_ban"] or "", r["tien_truoc_vat"], r["vat"], r["tong_cong"] or "",
                r["status"], r["uploaded_by"] or "", r["uploaded_at"], r["ghi_chu"] or ""]
        for c, v in enumerate(vals, start=1):
            cell = ws3.cell(row=i, column=c, value=v)
            cell.border = BORDER; cell.font = NORMAL
            cell.alignment = LEFT if c in (7,14) else CENTER
        ws3.cell(row=i,column=4).number_format = "dd/mm/yyyy"
        for c in (8,9,10): ws3.cell(row=i,column=c).number_format = "#,##0;(#,##0);-"
    ws3.freeze_panes = "B2"

    # Sheet 4: Dashboard
    ws4 = wb.create_sheet("4.Dashboard")
    ws4["A1"] = f"DASHBOARD TAM UNG & BO SUNG HD - Xuat ngay {today.strftime('%d/%m/%Y %H:%M')}"
    ws4["A1"].font = Font(name="Arial", bold=True, size=14, color="1F4E78")
    ws4.merge_cells("A1:D1"); ws4["A1"].alignment = CENTER

    n_tu = len(rows)
    sum_tu = sum(r["so_tien_tu"] for r in rows)
    sum_hd = conn.execute("SELECT COALESCE(SUM(tien_truoc_vat),0) FROM hoa_don WHERE status='approved'").fetchone()[0]
    qua_han = conn.execute("""SELECT COUNT(*) FROM tam_ung
        WHERE date(ngay_ket_thuc_hd, '-30 days') < date('now')
        AND ma_giai_ngan NOT IN (
            SELECT t.ma_giai_ngan FROM tam_ung t
            LEFT JOIN (SELECT ma_giai_ngan, SUM(tien_truoc_vat) AS s FROM hoa_don WHERE status='approved' GROUP BY ma_giai_ngan) h
            ON t.ma_giai_ngan = h.ma_giai_ngan
            WHERE COALESCE(h.s,0) >= t.so_tien_tu
        )""").fetchone()[0]

    kpis = [
        ("Tong so mon tam ung", n_tu),
        ("Tong gia tri tam ung (VND)", sum_tu),
        ("Tong HD da bo sung (VND)", sum_hd),
        ("Du can bo sung (VND)", max(sum_tu - sum_hd, 0)),
        ("Ty le bo sung", (sum_hd/sum_tu) if sum_tu else 0),
        ("So mon Qua han", qua_han),
    ]
    ws4["A3"] = "Chi tieu"; ws4["B3"] = "Gia tri"
    _style_header(ws4, 3, 2)
    for i, (lab, val) in enumerate(kpis, start=4):
        a = ws4.cell(row=i, column=1, value=lab); a.font = BOLD; a.border = BORDER; a.alignment = LEFT
        b = ws4.cell(row=i, column=2, value=val); b.font = NORMAL; b.border = BORDER; b.alignment = RIGHT
    ws4["B5"].number_format = "#,##0;(#,##0);-"
    ws4["B6"].number_format = "#,##0;(#,##0);-"
    ws4["B7"].number_format = "#,##0;(#,##0);-"
    ws4["B8"].number_format = "0.0%"
    ws4.column_dimensions["A"].width = 35
    ws4.column_dimensions["B"].width = 20

    conn.close()

    if output_path is None:
        output_path = f"export_tamung_{today.strftime('%Y%m%d_%H%M%S')}.xlsx"
    wb.save(output_path)
    return output_path


def export_to_drive_folder(drive_folder_path, filename_prefix="TamUng_TienDo"):
    """Export va copy sang folder Drive (folder local da sync voi Drive)."""
    today = date.today()
    fname = f"{filename_prefix}_{today.strftime('%Y%m%d_%H%M%S')}.xlsx"
    tmp_path = f"/tmp/{fname}" if os.name != 'nt' else fname
    export_excel(tmp_path)
    if not os.path.exists(drive_folder_path):
        os.makedirs(drive_folder_path, exist_ok=True)
    dest = os.path.join(drive_folder_path, fname)
    shutil.copy2(tmp_path, dest)
    # Cung copy them 1 ban "_latest" cho de truy cap
    latest = os.path.join(drive_folder_path, f"{filename_prefix}_LATEST.xlsx")
    shutil.copy2(tmp_path, latest)
    return dest, latest
