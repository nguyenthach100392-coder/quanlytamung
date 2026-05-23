# -*- coding: utf-8 -*-
"""Parser XML va PDF hoa don dien tu VN."""
import re
import os
import xml.etree.ElementTree as ET
from datetime import datetime


def _num(s):
    if s is None: return None
    s = str(s).strip().replace(" ", "")
    if not s: return None
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        if len(parts[-1]) == 3:
            s = s.replace(",", "")
        else:
            s = s.replace(",", ".")
    else:
        s = s.replace(".", "")
    try: return float(s)
    except: return None


def _parse_date(text):
    if not text: return None
    text = str(text)
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if m:
        y, mo, d = m.groups()
        try: return datetime(int(y), int(mo), int(d)).date()
        except: pass
    m = re.search(r"[Nn]g[aà]y[:\s]*(\d{1,2})[/-](\d{1,2})[/-](\d{4})", text)
    if m:
        d, mo, y = m.groups()
        try: return datetime(int(y), int(mo), int(d)).date()
        except: pass
    m = re.search(r"(\d{1,2})\s*th[aá]ng\s*(\d{1,2})\s*n[aă]m\s*(\d{4})", text, re.IGNORECASE)
    if m:
        d, mo, y = m.groups()
        try: return datetime(int(y), int(mo), int(d)).date()
        except: pass
    m = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", text)
    if m:
        d, mo, y = m.groups()
        try: return datetime(int(y), int(mo), int(d)).date()
        except: pass
    return None


def _findtext_any(root, tags):
    tags_lower = [t.lower() for t in tags]
    for el in root.iter():
        tag = el.tag.split("}")[-1].lower()
        if tag in tags_lower and el.text:
            return el.text.strip()
    return None


def parse_xml(path_or_bytes, filename=None):
    """Parse VN e-invoice XML (TT78)."""
    result = {
        "file": filename or (path_or_bytes if isinstance(path_or_bytes, str) else "stream.xml"),
        "so_hd": None, "ngay_hd": None,
        "mst_ban": None, "ten_ban": None,
        "tien_truoc_vat": None, "vat": None, "tong_cong": None,
        "ma_tra_cuu": None, "parse_status": "OK",
    }
    try:
        if isinstance(path_or_bytes, (bytes, bytearray)):
            root = ET.fromstring(path_or_bytes)
        else:
            tree = ET.parse(path_or_bytes)
            root = tree.getroot()
    except Exception as e:
        result["parse_status"] = f"Loi XML: {e}"
        return result

    so = _findtext_any(root, ["SHDon", "InvoiceNumber", "InvoiceNo", "SoHD"])
    if so: result["so_hd"] = so
    result["ngay_hd"] = _parse_date(_findtext_any(root, ["NLap", "InvoiceDate", "NgayLap", "NgayHD"]))

    seller_block = None
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag in ("NBan", "Seller", "NguoiBan"):
            seller_block = el
            break
    if seller_block is not None:
        result["mst_ban"] = _findtext_any(seller_block, ["MST", "TaxCode"])
        result["ten_ban"] = _findtext_any(seller_block, ["Ten", "Name", "TenDV"])

    pre = _findtext_any(root, ["TgTCThue", "TotalAmountWithoutVAT", "TongTienChuaThue"])
    if pre: result["tien_truoc_vat"] = _num(pre)
    vat = _findtext_any(root, ["TgTThue", "TotalVATAmount", "TongTienThue"])
    if vat: result["vat"] = _num(vat)
    tot = _findtext_any(root, ["TgTTTBSo", "TotalAmount", "TongTienThanhToan"])
    if tot: result["tong_cong"] = _num(tot)
    mtc = _findtext_any(root, ["MCCQT", "MaTraCuu"])
    if mtc: result["ma_tra_cuu"] = mtc

    missing = [k for k in ("so_hd","ngay_hd","tien_truoc_vat","vat") if not result.get(k)]
    if missing:
        result["parse_status"] = "Thieu: " + ", ".join(missing)
    return result


def parse_pdf(path_or_bytes, filename=None):
    result = {
        "file": filename or (path_or_bytes if isinstance(path_or_bytes, str) else "stream.pdf"),
        "so_hd": None, "ngay_hd": None,
        "mst_ban": None, "ten_ban": None,
        "tien_truoc_vat": None, "vat": None, "tong_cong": None,
        "ma_tra_cuu": None, "parse_status": "OK",
    }
    try:
        import pdfplumber
        import io
        if isinstance(path_or_bytes, (bytes, bytearray)):
            pdf = pdfplumber.open(io.BytesIO(path_or_bytes))
        else:
            pdf = pdfplumber.open(path_or_bytes)
        text = "\n".join((p.extract_text() or "") for p in pdf.pages)
        pdf.close()
    except Exception as e:
        result["parse_status"] = f"Loi PDF: {e}"
        return result

    m = re.search(r"S[ốo][:\s]+(\w[\w/-]*)", text)
    if m: result["so_hd"] = m.group(1).strip()
    result["ngay_hd"] = _parse_date(text)

    m = re.search(r"M[aã]\s*s[ốo]\s*thu[ếe][:\s]+(\d{10}(?:-\d{3})?)", text, re.IGNORECASE)
    if m: result["mst_ban"] = m.group(1)
    m = re.search(r"(?:Đ[ơo]n v[ịi] b[áa]n h[àa]ng|T[êe]n ng[ưu][ờo]i b[áa]n|Seller)[:\s]+(.+)", text)
    if m: result["ten_ban"] = m.group(1).split("\n")[0].strip()[:100]

    for p in [r"C[ộo]ng ti[ềe]n h[àa]ng[:\s]*([\d.,]+)",
              r"T[ổo]ng ti[ềe]n\s*\(?ch[ưu]a[^)]*thu[ếe][^)]*\)?[:\s]*([\d.,]+)",
              r"T[ổo]ng ti[ềe]n h[àa]ng[:\s]*([\d.,]+)"]:
        m = re.search(p, text, re.IGNORECASE)
        if m: result["tien_truoc_vat"] = _num(m.group(1)); break
    for p in [r"Ti[ềe]n thu[ếe]\s*GTGT[:\s]*([\d.,]+)",
              r"Thu[ếe]\s*GTGT[:\s]*([\d.,]+)"]:
        m = re.search(p, text, re.IGNORECASE)
        if m: result["vat"] = _num(m.group(1)); break
    for p in [r"T[ổo]ng c[ộo]ng\s*ti[ềe]n\s*thanh\s*to[áa]n[:\s]*([\d.,]+)",
              r"T[ổo]ng\s*thanh\s*to[áa]n[:\s]*([\d.,]+)"]:
        m = re.search(p, text, re.IGNORECASE)
        if m: result["tong_cong"] = _num(m.group(1)); break
    m = re.search(r"M[ãa]\s*tra\s*c[ứu]u[:\s]+(\w+)", text, re.IGNORECASE)
    if m: result["ma_tra_cuu"] = m.group(1)

    missing = [k for k in ("so_hd","ngay_hd","tien_truoc_vat","vat") if not result.get(k)]
    if missing:
        result["parse_status"] = "Thieu: " + ", ".join(missing)
    return result


def parse_file(uploaded_file):
    """Parse 1 file upload tu Streamlit (UploadedFile object)."""
    name = uploaded_file.name
    data = uploaded_file.read()
    if name.lower().endswith(".xml"):
        return parse_xml(data, name)
    elif name.lower().endswith(".pdf"):
        return parse_pdf(data, name)
    else:
        return {"file": name, "parse_status": "Khong ho tro dinh dang"}
