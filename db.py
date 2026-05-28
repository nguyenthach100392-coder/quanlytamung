# -*- coding: utf-8 -*-
"""SQLite database layer cho he thong theo doi tam ung (Quan ly theo Hop Dong)."""
import psycopg2
import psycopg2.extras
import os
import re
from datetime import datetime, date
import streamlit as st

DB_PATH = "tamung.db"


SUPABASE_URL = "postgresql://postgres.wtuomrtntyqchixeqxrp:%21Thach1003%21@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres"

def get_conn():
    conn = psycopg2.connect(SUPABASE_URL)
    conn.autocommit = False # We manage commits manually as before
    return conn

# Helper class to support `with get_conn() as c:` returning a DictCursor
import contextlib
from psycopg2.pool import ThreadedConnectionPool

_pool = None
def get_pool():
    global _pool
    if _pool is None:
        _pool = ThreadedConnectionPool(1, 20, SUPABASE_URL)
    return _pool

@contextlib.contextmanager
def get_conn():
    pool = get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)

def init_db():
    pass


def list_distinct_companies():
    """Lay danh sach ten cong ty da co (distinct)."""
    with get_conn() as c:
        c.execute("""
            SELECT khach_hang FROM hop_dong WHERE khach_hang IS NOT NULL AND khach_hang != ''
            UNION
            SELECT don_vi_thu_huong FROM hop_dong WHERE don_vi_thu_huong IS NOT NULL AND don_vi_thu_huong != ''
            UNION
            SELECT ten_ban FROM hoa_don WHERE ten_ban IS NOT NULL AND ten_ban != ''
            ORDER BY 1
        """)
        rows = c.fetchall()
        return [list(r.values())[0] for r in rows]


def find_similar_company(name):
    normalized = normalize_company_name(name)
    with get_conn() as c:
        c.execute(
            "SELECT company_name FROM company_registry WHERE normalized_name=%s ORDER BY id DESC LIMIT 1",
            (normalized,)
        )
        row = c.fetchone()
        return list(row.values())[0] if row else None


def get_or_create_company_seq(khach_hang, year):
    normalized = normalize_company_name(khach_hang)
    with get_conn() as c:
        c.execute(
            "SELECT company_seq FROM company_registry WHERE normalized_name=%s AND year=%s",
            (normalized, year)
        )
        existing = c.fetchone()
        
        if existing:
            return list(existing.values())[0]
            
        c.execute(
            "SELECT COALESCE(MAX(company_seq), 0) FROM company_registry WHERE year=%s",
            (year,)
        )
        max_seq = list(c.fetchone().values())[0]
        company_seq = max_seq + 1
        c.execute(
            "INSERT INTO company_registry (company_name, normalized_name, company_seq, year) VALUES (%s,%s,%s,%s)",
            (khach_hang.strip(), normalized, company_seq, year)
        )
        return company_seq

def find_hop_dong_by_so(khach_hang, so_hd):
    """Tim hop dong da ton tai theo khach hang va so_hd."""
    if not so_hd: return None
    with get_conn() as c:
        c.execute("SELECT * FROM hop_dong WHERE khach_hang=%s AND so_hd=%s", (khach_hang, so_hd))
        return c.fetchone()

def generate_ma_hop_dong(khach_hang, year=None):
    if year is None: year = date.today().year
    company_seq = get_or_create_company_seq(khach_hang, year)
    with get_conn() as c:
        prefix = f"HD-{year}-{company_seq:03d}."
        c.execute("SELECT ma_hop_dong FROM hop_dong WHERE ma_hop_dong LIKE %s", (f"{prefix}%",))
        rows = c.fetchall()
        max_idx = 0
        for r in rows:
            try:
                idx = int(r.get("ma_hop_dong").split(".")[-1])
                if idx > max_idx: max_idx = idx
            except: pass
        return f"{prefix}{max_idx+1:02d}"


def generate_ma_giai_ngan(khach_hang, year=None):
    if year is None: year = date.today().year
    company_seq = get_or_create_company_seq(khach_hang, year)
    with get_conn() as c:
        prefix = f"TU-{year}-{company_seq:03d}."
        c.execute("SELECT ma_giai_ngan FROM tam_ung WHERE ma_giai_ngan LIKE %s", (f"{prefix}%",))
        rows = c.fetchall()
        max_idx = 0
        for r in rows:
            try:
                idx = int(r.get("ma_giai_ngan").split(".")[-1])
                if idx > max_idx: max_idx = idx
            except: pass
        return f"{prefix}{max_idx+1:02d}"

# ---- Users ----
def list_users():
    with get_conn() as c:
        c.execute("SELECT * FROM users WHERE active=1 ORDER BY role, full_name")
        return c.fetchall()


def get_user(username):
    with get_conn() as c:
        c.execute("SELECT * FROM users WHERE username=%s", (username,))
        return c.fetchone()


# ---- Hop dong ----
def list_hop_dong(phong=None):
    with get_conn() as c:
        if phong:
            c.execute(
                "SELECT * FROM hop_dong WHERE phong_phu_trach=%s ORDER BY created_at DESC", (phong,)
            )
            return c.fetchall()
        c.execute("SELECT * FROM hop_dong ORDER BY created_at DESC")
        return c.fetchall()


def get_hop_dong(ma):
    with get_conn() as c:
        c.execute("SELECT * FROM hop_dong WHERE ma_hop_dong=%s", (ma,))
        return c.fetchone()


def add_hop_dong(data, user):
    with get_conn() as c:
        c.execute("""INSERT INTO hop_dong
            (ma_hop_dong, khach_hang, cif, don_vi_thu_huong, so_hd, gia_tri_hd,
             ngay_hop_dong, ngay_ket_thuc_hd, loai_tu, loai_gia_tri_kt, pct_khau_tru, phong_phu_trach, ghi_chu, khe_uoc_vay, created_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (data.get("ma_hop_dong"), data.get("khach_hang"), data.get("cif"), data.get("don_vi_thu_huong"), data.get("so_hd"),
             data.get("gia_tri_hd"), data.get("ngay_hop_dong"), data.get("ngay_ket_thuc_hd"),
             data.get("loai_tu", "khau_tru_dot"), data.get("loai_gia_tri_kt", "Trước VAT"),
             data.get("pct_khau_tru", 10.0), data.get("phong_phu_trach"), data.get("ghi_chu"), data.get("khe_uoc_vay"), user))
        log(c, "ADD_HOP_DONG", "hop_dong", data.get("ma_hop_dong"), user, "")


# ---- Tam ung (Giai ngan) ----
def list_tam_ung(ma_hop_dong):
    with get_conn() as c:
        c.execute("SELECT * FROM tam_ung WHERE ma_hop_dong=%s ORDER BY ngay_giai_ngan ASC", (ma_hop_dong,))
        return c.fetchall()


def add_tam_ung(data, user):
    with get_conn() as c:
        c.execute("""INSERT INTO tam_ung
            (ma_giai_ngan, ma_hop_dong, so_tien_tu, ngay_giai_ngan, ghi_chu, created_by)
            VALUES (%s,%s,%s,%s,%s,%s)""",
            (data.get("ma_giai_ngan"), data.get("ma_hop_dong"), data.get("so_tien_tu"),
             data.get("ngay_giai_ngan"), data.get("ghi_chu"), user))
        log(c, "ADD_GIAI_NGAN", "tam_ung", data.get("ma_giai_ngan"), user, f"Vào HD {data.get('ma_hop_dong')}")

def update_tam_ung_ghi_chu(ma_giai_ngan, ghi_chu):
    with get_conn() as c:
        c.execute("UPDATE tam_ung SET ghi_chu=%s WHERE ma_giai_ngan=%s", (ghi_chu, ma_giai_ngan))


def delete_hop_dong(ma, user):
    with get_conn() as c:
        # Xóa các bảng con trước để tránh lỗi Foreign Key
        c.execute("DELETE FROM tam_ung WHERE ma_hop_dong=%s", (ma,))
        c.execute("DELETE FROM hoa_don WHERE ma_hop_dong=%s", (ma,))
        c.execute("DELETE FROM hstt WHERE ma_hop_dong=%s", (ma,))
        c.execute("DELETE FROM staging_hd WHERE ma_hop_dong=%s", (ma,))
        # Sau đó xóa bảng cha
        c.execute("DELETE FROM hop_dong WHERE ma_hop_dong=%s", (ma,))
        log(c, "DEL_HOP_DONG", "hop_dong", ma, user, "")


# ---- HSTT ----
def list_hstt(ma_hop_dong=None):
    with get_conn() as c:
        if ma_hop_dong:
            c.execute("SELECT * FROM hstt WHERE ma_hop_dong=%s ORDER BY dot_so", (ma_hop_dong,))
            return c.fetchall()
        c.execute("SELECT * FROM hstt ORDER BY ma_hop_dong, dot_so")
        return c.fetchall()


def add_hstt(data, user):
    with get_conn() as c:
        c.execute("""INSERT INTO hstt
            (ma_hop_dong, dot_so, ngay_hstt, kl_truoc_vat, vat, tong_cong, loai_kl, ghi_chu, created_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (data.get("ma_hop_dong"), data.get("dot_so"), data.get("ngay_hstt"),
             data.get("kl_truoc_vat"), data.get("vat", 0), data.get("tong_cong", data.get("kl_truoc_vat")),
             data.get("loai_kl", "Trước VAT"), data.get("ghi_chu"), user))
        log(c, "ADD_HSTT", "hstt", f"{data.get('ma_hop_dong')}/dot{data.get('dot_so')}", user, "")

def update_hstt(hstt_id, data, user):
    with get_conn() as c:
        c.execute("""UPDATE hstt
            SET dot_so=%s, ngay_hstt=%s, kl_truoc_vat=%s, vat=%s, tong_cong=%s, ghi_chu=%s, loai_kl=%s
            WHERE id=%s""",
            (data.get("dot_so"), data.get("ngay_hstt"), data.get("kl_truoc_vat"), data.get("vat", 0),
             data.get("tong_cong", data.get("kl_truoc_vat")), data.get("ghi_chu"), data.get("loai_kl", "Trước VAT"), hstt_id))
        log(c, "UPDATE_HSTT", "hstt", str(hstt_id), user, "")

def delete_hstt(hstt_id, user):
    with get_conn() as c:
        c.execute("DELETE FROM hstt WHERE id=%s", (hstt_id,))
        log(c, "DELETE_HSTT", "hstt", str(hstt_id), user, "")


# ---- Hoa don ----
def list_hoa_don(ma_hop_dong=None, dot=None, status=None):
    q = "SELECT * FROM hoa_don WHERE 1=1"
    args = []
    if ma_hop_dong: q += " AND ma_hop_dong=%s"; args.append(ma_hop_dong)
    if dot is not None: q += " AND dot_so=%s"; args.append(dot)
    if status: q += " AND status=%s"; args.append(status)
    q += " ORDER BY uploaded_at DESC"
    with get_conn() as c:
        c.execute(q, args)
        return c.fetchall()


def add_hoa_don(data, user, status="approved"):
    with get_conn() as c:
        c.execute("""INSERT INTO hoa_don
            (ma_hop_dong, dot_so, so_hd, ngay_hd, mst_ban, ten_ban,
             tien_truoc_vat, vat, tong_cong, ma_tra_cuu, file_src,
             status, uploaded_by, approved_by, approved_at, ghi_chu)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (data.get("ma_hop_dong"), data.get("dot_so", 1), data.get("so_hd"), data.get("ngay_hd"),
             data.get("mst_ban"), data.get("ten_ban"),
             data.get("tien_truoc_vat"), data.get("vat"), data.get("tong_cong"),
             data.get("ma_tra_cuu"), data.get("file_src"),
             status, user,
             user if status == "approved" else None,
             datetime.now() if status == "approved" else None,
             data.get("ghi_chu")))
        log(c, "ADD_HOA_DON", "hoa_don", data.get("so_hd"), user, "")


def approve_hoa_don(hd_id, user):
    with get_conn() as c:
        c.execute("UPDATE hoa_don SET status='approved', approved_by=%s, approved_at=%s WHERE id=%s",
                  (user, datetime.now(), hd_id))


def reject_hoa_don(hd_id, user, reason=""):
    with get_conn() as c:
        c.execute("UPDATE hoa_don SET status='rejected', approved_by=%s, approved_at=%s, ghi_chu=%s WHERE id=%s",
                  (user, datetime.now(), reason, hd_id))


# ---- Staging ----
def add_staging(data, user):
    with get_conn() as c:
        c.execute("""INSERT INTO staging_hd 
            (ma_hop_dong, dot_so, so_hd, ngay_hd, mst_ban, ten_ban, tien_truoc_vat, vat, tong_cong,
             ma_tra_cuu, file_src, parse_status, uploaded_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (data.get("ma_hop_dong"), data.get("dot_so"), data.get("so_hd"), data.get("ngay_hd"), data.get("mst_ban"),
             data.get("ten_ban"), data.get("tien_truoc_vat"), data.get("vat"),
             data.get("tong_cong"), data.get("ma_tra_cuu"),
             data.get("file_src"), data.get("parse_status"), user))
        c.execute("SELECT LASTVAL()")
        return c.fetchone()["lastval"]


def list_staging(user=None):
    with get_conn() as c:
        if user:
            c.execute("SELECT * FROM staging_hd WHERE uploaded_by=%s ORDER BY uploaded_at DESC", (user,))
            return c.fetchall()
        c.execute("SELECT * FROM staging_hd ORDER BY uploaded_at DESC")
        return c.fetchall()


def delete_staging(staging_id):
    with get_conn() as c:
        c.execute("DELETE FROM staging_hd WHERE id=%s", (staging_id,))


def delete_hoa_don(hd_id, user):
    with get_conn() as c:
        c.execute("DELETE FROM hoa_don WHERE id=%s", (hd_id,))


def get_staging(staging_id):
    with get_conn() as c:
        c.execute("SELECT * FROM staging_hd WHERE id=%s", (staging_id,))
        return c.fetchone()


# ---- Calc helpers ----
def calc_summary(ma_hop_dong):
    """Tinh luy ke giai ngan, khau tru, HD bo sung, du can bo sung cho 1 Hop Dong."""
    with get_conn() as c:
        c.execute("SELECT * FROM hop_dong WHERE ma_hop_dong=%s", (ma_hop_dong,))
        hd = c.fetchone()
        if not hd: return None
        
        # Tong tien da giai ngan cho HD nay
        c.execute(
            "SELECT COALESCE(SUM(so_tien_tu), 0), MIN(ngay_giai_ngan) FROM tam_ung WHERE ma_hop_dong=%s",
            (ma_hop_dong,)
        )
        gn_row = c.fetchone()
        tong_giai_ngan = list(gn_row.values())[0]
        ngay_gn_dau = list(gn_row.values())[1]
        
        pct = (hd.get("pct_khau_tru") or 0) / 100.0
        loai_kt = hd.get("loai_gia_tri_kt") if hd.get("loai_gia_tri_kt") else "Trước VAT"
        if loai_kt == "Sau VAT":
            c.execute(
                "SELECT COALESCE(SUM(COALESCE(tong_cong, kl_truoc_vat) * %s),0) FROM hstt WHERE ma_hop_dong=%s",
                (pct, ma_hop_dong)
            )
            kt_luy_ke = list(c.fetchone().values())[0]
        else:
            c.execute(
                "SELECT COALESCE(SUM(kl_truoc_vat * %s),0) FROM hstt WHERE ma_hop_dong=%s",
                (pct, ma_hop_dong)
            )
            kt_luy_ke = list(c.fetchone().values())[0]
        
        hd_pct = 1.0 if hd["loai_tu"] == "mot_lan" else pct
        hd_loai_kt = "Trước VAT" if hd["loai_tu"] == "mot_lan" else loai_kt
        
        if hd_loai_kt == "Sau VAT":
            c.execute(
                "SELECT COALESCE(SUM(COALESCE(tong_cong, tien_truoc_vat) * %s),0) FROM hoa_don WHERE ma_hop_dong=%s AND status='approved'",
                (hd_pct, ma_hop_dong)
            )
            hd_luy_ke = list(c.fetchone().values())[0]
        else:
            c.execute(
                "SELECT COALESCE(SUM(tien_truoc_vat * %s),0) FROM hoa_don WHERE ma_hop_dong=%s AND status='approved'",
                (hd_pct, ma_hop_dong)
            )
            hd_luy_ke = list(c.fetchone().values())[0]
        
        du = max(tong_giai_ngan - hd_luy_ke, 0)
        pct_done = hd_luy_ke / tong_giai_ngan if tong_giai_ngan > 0 else 0
        
        return {
            "tong_giai_ngan": tong_giai_ngan,
            "ngay_giai_ngan_dau": ngay_gn_dau,
            "loai_tu": hd.get("loai_tu"),
            "khau_tru_luy_ke": kt_luy_ke,
            "hd_luy_ke": hd_luy_ke,
            "du_can_bo_sung": du,
            "pct_hoan_thanh": pct_done,
        }


# ---- Audit ----
def log(conn, action, entity, entity_id, username, details):
    conn.execute(
        "INSERT INTO audit_log (action, entity, entity_id, username, details) VALUES (%s,%s,%s,%s,%s)",
        (action, entity, entity_id, username, details)
    )

def log_action(action, entity, entity_id, username, details):
    with get_conn() as c:
        log(c, action, entity, entity_id, username, details)

def recent_audit(limit=50):
    with get_conn() as c:
        c.execute("SELECT * FROM audit_log ORDER BY ts DESC LIMIT %s", (limit,))
        return c.fetchall()

def add_dashboard_logs(data, user):
    with get_conn() as c:
        c.execute("""INSERT INTO dashboard_logs
            (loai_hoat_dong, chi_tiet, ma_hop_dong, created_by)
            VALUES (%s,%s,%s,%s)""",
            (data.get("loai_hoat_dong"), data.get("chi_tiet"), data.get("ma_hop_dong"), user))

def list_dashboard_logs(limit=20):
    with get_conn() as c:
        c.execute("SELECT * FROM dashboard_logs ORDER BY created_at DESC LIMIT %s", (limit,))
        return c.fetchall()

def get_distinct_upload_dates(phong=None):
    with get_conn() as c:
        if phong:
            c.execute("""
                SELECT DISTINCT (h.uploaded_at + interval '7 hours')::date as d 
                FROM hoa_don h
                JOIN hop_dong hd ON h.ma_hop_dong = hd.ma_hop_dong
                WHERE h.uploaded_at IS NOT NULL AND hd.phong_phu_trach = %s
                ORDER BY d DESC
            """, (phong,))
        else:
            c.execute("""
                SELECT DISTINCT (uploaded_at + interval '7 hours')::date as d 
                FROM hoa_don 
                WHERE uploaded_at IS NOT NULL
                ORDER BY d DESC
            """)
        return [r.get("d") for r in c.fetchall() if r.get("d")]

def get_hoadons_by_date_str(date_str, phong=None):
    with get_conn() as c:
        if phong:
            c.execute("""
                SELECT h.* 
                FROM hoa_don h
                JOIN hop_dong hd ON h.ma_hop_dong = hd.ma_hop_dong
                WHERE (h.uploaded_at + interval '7 hours')::date = %s AND hd.phong_phu_trach = %s
                ORDER BY h.uploaded_at DESC
            """, (date_str, phong))
            return c.fetchall()
        else:
            c.execute("""
                SELECT * FROM hoa_don 
                WHERE (uploaded_at + interval '7 hours')::date = %s
                ORDER BY uploaded_at DESC
            """, (date_str,))
            return c.fetchall()


def bulk_calc_summary(hd_list):
    ma_list = tuple([r.get('ma_hop_dong') for r in hd_list])
    if not ma_list: return {}
    
    with get_conn() as c:
        c.execute('SELECT ma_hop_dong, COALESCE(SUM(so_tien_tu), 0) as tong_gn, MIN(ngay_giai_ngan) as min_ngay FROM tam_ung WHERE ma_hop_dong IN %s GROUP BY ma_hop_dong', (ma_list,))
        gn_rows = {r['ma_hop_dong']: r for r in c.fetchall()}
        
        c.execute('SELECT ma_hop_dong, COALESCE(SUM(kl_truoc_vat),0) as sum_kl, COALESCE(SUM(COALESCE(tong_cong, kl_truoc_vat)),0) as sum_tong FROM hstt WHERE ma_hop_dong IN %s GROUP BY ma_hop_dong', (ma_list,))
        hstt_rows = {r['ma_hop_dong']: r for r in c.fetchall()}
        
        c.execute("SELECT ma_hop_dong, COALESCE(SUM(tien_truoc_vat),0) as sum_tien, COALESCE(SUM(COALESCE(tong_cong, tien_truoc_vat)),0) as sum_tong FROM hoa_don WHERE status='approved' AND ma_hop_dong IN %s GROUP BY ma_hop_dong", (ma_list,))
        hd_rows = {r['ma_hop_dong']: r for r in c.fetchall()}
        
    res = {}
    for hd in hd_list:
        ma = hd.get('ma_hop_dong')
        gn_row = gn_rows.get(ma)
        if not gn_row:
            tong_giai_ngan = 0
            ngay_gn_dau = None
        else:
            tong_giai_ngan = gn_row['tong_gn']
            ngay_gn_dau = gn_row['min_ngay']
            
        pct = (hd.get('pct_khau_tru') or 0) / 100.0
        loai_kt = hd.get('loai_gia_tri_kt') if hd.get('loai_gia_tri_kt') else 'Trước VAT'
        
        hstt_row = hstt_rows.get(ma)
        if not hstt_row: kt_luy_ke = 0
        else:
            if loai_kt == 'Sau VAT': kt_luy_ke = hstt_row['sum_tong'] * pct
            else: kt_luy_ke = hstt_row['sum_kl'] * pct
            
        hd_pct = 1.0 if hd.get('loai_tu') == 'mot_lan' else pct
        hd_loai_kt = 'Trước VAT' if hd.get('loai_tu') == 'mot_lan' else loai_kt
        
        hdr = hd_rows.get(ma)
        if not hdr: hd_luy_ke = 0
        else:
            if hd_loai_kt == 'Sau VAT': hd_luy_ke = hdr['sum_tong'] * hd_pct
            else: hd_luy_ke = hdr['sum_tien'] * hd_pct
            
        du = max(tong_giai_ngan - hd_luy_ke, 0)
        res[ma] = {
            'tong_giai_ngan': tong_giai_ngan,
            'ngay_giai_ngan_dau': ngay_gn_dau,
            'khau_tru_luy_ke': kt_luy_ke,
            'hd_luy_ke': hd_luy_ke,
            'du_can_bo_sung': du,
            'pct_hoan_thanh': hd_luy_ke / tong_giai_ngan if tong_giai_ngan else 0.0
        }
    return res
