# -*- coding: utf-8 -*-
"""SQLite database layer cho he thong theo doi tam ung (Quan ly theo Hop Dong)."""
import sqlite3
import os
import re
from datetime import datetime, date

DB_PATH = os.environ.get("TAMUNG_DB", "tamung.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Khoi tao schema."""
    conn = get_conn()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL DEFAULT '123456',
        full_name TEXT NOT NULL,
        dept TEXT,
        role TEXT NOT NULL CHECK (role IN ('phong_kh', 'qttd', 'admin')),
        active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS company_registry (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_name TEXT NOT NULL,
        normalized_name TEXT NOT NULL,
        company_seq INTEGER NOT NULL,
        year INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(year, company_seq),
        UNIQUE(year, normalized_name)
    );

    CREATE TABLE IF NOT EXISTS hop_dong (
        ma_hop_dong TEXT PRIMARY KEY,
        khach_hang TEXT NOT NULL,
        cif TEXT,
        don_vi_thu_huong TEXT,
        so_hd TEXT,
        gia_tri_hd REAL,
        ngay_ket_thuc_hd DATE NOT NULL,
        loai_tu TEXT NOT NULL DEFAULT 'khau_tru_dot',
        pct_khau_tru REAL DEFAULT 0.1,
        phong_phu_trach TEXT,
        ghi_chu TEXT,
        created_by TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS tam_ung (
        ma_giai_ngan TEXT PRIMARY KEY,
        ma_hop_dong TEXT,
        so_tien_tu REAL NOT NULL,
        ngay_giai_ngan DATE NOT NULL,
        ghi_chu TEXT,
        created_by TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (ma_hop_dong) REFERENCES hop_dong(ma_hop_dong)
    );

    CREATE TABLE IF NOT EXISTS hstt (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ma_hop_dong TEXT NOT NULL,
        dot_so INTEGER NOT NULL,
        ngay_hstt DATE NOT NULL,
        kl_truoc_vat REAL NOT NULL,
        ghi_chu TEXT,
        created_by TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (ma_hop_dong) REFERENCES hop_dong(ma_hop_dong),
        UNIQUE(ma_hop_dong, dot_so)
    );

    CREATE TABLE IF NOT EXISTS hoa_don (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ma_hop_dong TEXT NOT NULL,
        dot_so INTEGER NOT NULL DEFAULT 1,
        so_hd TEXT NOT NULL,
        ngay_hd DATE NOT NULL,
        mst_ban TEXT,
        ten_ban TEXT,
        tien_truoc_vat REAL NOT NULL,
        vat REAL NOT NULL,
        tong_cong REAL,
        ma_tra_cuu TEXT,
        file_src TEXT,
        status TEXT DEFAULT 'approved',
        uploaded_by TEXT,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        approved_by TEXT,
        approved_at TIMESTAMP,
        ghi_chu TEXT,
        FOREIGN KEY (ma_hop_dong) REFERENCES hop_dong(ma_hop_dong)
    );

    CREATE TABLE IF NOT EXISTS staging_hd (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ma_hop_dong TEXT,
        dot_so INTEGER,
        so_hd TEXT,
        ngay_hd DATE,
        mst_ban TEXT,
        ten_ban TEXT,
        tien_truoc_vat REAL,
        vat REAL,
        tong_cong REAL,
        ma_tra_cuu TEXT,
        file_src TEXT,
        parse_status TEXT,
        uploaded_by TEXT,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action TEXT NOT NULL,
        entity TEXT,
        entity_id TEXT,
        username TEXT,
        details TEXT,
        ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Seed default users
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        c.executemany(
            "INSERT INTO users (username, password, full_name, dept, role) VALUES (?,?,?,?,?)",
            [
                ("admin", "admin@123", "Quan tri he thong", "QTTD", "admin"),
                ("qttd01", "qttd01@123", "Can bo QTTD 01", "QTTD", "qttd"),
            ]
        )
        
    # Xóa 2 user mặc định cũ không cần dùng nữa (để nó biến mất trên Web)
    c.execute("DELETE FROM users WHERE username IN ('phongkh_dn', 'phongkh_sme')")
    
    # Fix dữ liệu cũ: lúc trước pct_khau_tru lưu dưới dạng thập phân (vd: 0.1), giờ đổi thành phần trăm (10.0)
    c.execute("UPDATE hop_dong SET pct_khau_tru = pct_khau_tru * 100 WHERE pct_khau_tru < 1.0 AND pct_khau_tru > 0")
        
    # MIGRATIONS: Add new columns if they don't exist
    def add_col_if_not_exists(table, col_name, col_type):
        c.execute(f"PRAGMA table_info({table})")
        cols = [r["name"] for r in c.fetchall()]
        if col_name not in cols:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")

    add_col_if_not_exists("hop_dong", "cif", "TEXT")
    add_col_if_not_exists("hop_dong", "don_vi_thu_huong", "TEXT")
    add_col_if_not_exists("hop_dong", "loai_gia_tri_kt", "TEXT")
    add_col_if_not_exists("hstt", "vat", "REAL")
    add_col_if_not_exists("hstt", "tong_cong", "REAL")
    add_col_if_not_exists("hstt", "loai_kl", "TEXT")
    
    conn.commit()
    conn.close()


# ---- Company name normalization ----
def normalize_company_name(name):
    """Chuan hoa ten cong ty de so sanh: bo tien to, loai hinh, uppercase, trim."""
    s = name.strip().upper()
    prefixes = [
        r'CONG\s+TY\s+CO\s+PHAN\s+',
        r'CONG\s+TY\s+TNHH\s+MTV\s+',
        r'CONG\s+TY\s+TNHH\s+',
        r'CONG\s+TY\s+CP\s+',
        r'CONG\s+TY\s+',
        r'CTCP\s+',
        r'CTTNHH\s+',
        r'CT\s+',
        r'DOANH\s+NGHIEP\s+TU\s+NHAN\s+',
        r'DOANH\s+NGHIEP\s+',
        r'DNTN\s+',
        r'DN\s+',
    ]
    for p in prefixes:
        s2 = re.sub(r'^' + p, '', s, count=1)
        if s2 != s:
            s = s2
            break
    for kw in ['TNHH MTV', 'TNHH', 'CO PHAN', 'CP', 'MTV']:
        s = re.sub(r'\b' + kw + r'\b', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def list_distinct_companies():
    """Lay danh sach ten cong ty da co (distinct)."""
    with get_conn() as c:
        rows = c.execute("""
            SELECT khach_hang FROM hop_dong WHERE khach_hang IS NOT NULL AND khach_hang != ''
            UNION
            SELECT don_vi_thu_huong FROM hop_dong WHERE don_vi_thu_huong IS NOT NULL AND don_vi_thu_huong != ''
            UNION
            SELECT ten_ban FROM hoa_don WHERE ten_ban IS NOT NULL AND ten_ban != ''
            ORDER BY 1
        """).fetchall()
        return [r[0] for r in rows]


def find_similar_company(name):
    normalized = normalize_company_name(name)
    with get_conn() as c:
        row = c.execute(
            "SELECT company_name FROM company_registry WHERE normalized_name=? ORDER BY id DESC LIMIT 1",
            (normalized,)
        ).fetchone()
        return row[0] if row else None


def get_or_create_company_seq(khach_hang, year):
    normalized = normalize_company_name(khach_hang)
    with get_conn() as c:
        existing = c.execute(
            "SELECT company_seq FROM company_registry WHERE normalized_name=? AND year=?",
            (normalized, year)
        ).fetchone()
        
        if existing:
            return existing[0]
            
        max_seq = c.execute(
            "SELECT COALESCE(MAX(company_seq), 0) FROM company_registry WHERE year=?",
            (year,)
        ).fetchone()[0]
        company_seq = max_seq + 1
        c.execute(
            "INSERT INTO company_registry (company_name, normalized_name, company_seq, year) VALUES (?,?,?,?)",
            (khach_hang.strip(), normalized, company_seq, year)
        )
        return company_seq

def find_hop_dong_by_so(khach_hang, so_hd):
    """Tim hop dong da ton tai theo khach hang va so_hd."""
    if not so_hd: return None
    with get_conn() as c:
        return c.execute("SELECT * FROM hop_dong WHERE khach_hang=? AND so_hd=?", (khach_hang, so_hd)).fetchone()

def generate_ma_hop_dong(khach_hang, year=None):
    if year is None: year = date.today().year
    company_seq = get_or_create_company_seq(khach_hang, year)
    with get_conn() as c:
        count = c.execute("SELECT COUNT(*) FROM hop_dong WHERE ma_hop_dong LIKE ?", (f"HD-{year}-{company_seq:03d}.%",)).fetchone()[0]
        return f"HD-{year}-{company_seq:03d}.{count+1:02d}"

def generate_ma_giai_ngan(khach_hang, year=None):
    if year is None: year = date.today().year
    company_seq = get_or_create_company_seq(khach_hang, year)
    with get_conn() as c:
        count = c.execute("SELECT COUNT(*) FROM tam_ung WHERE ma_giai_ngan LIKE ?", (f"TU-{year}-{company_seq:03d}.%",)).fetchone()[0]
        return f"TU-{year}-{company_seq:03d}.{count+1:02d}"


# ---- Users ----
def list_users():
    with get_conn() as c:
        return c.execute("SELECT * FROM users WHERE active=1 ORDER BY role, full_name").fetchall()


def get_user(username):
    with get_conn() as c:
        return c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()


# ---- Hop dong ----
def list_hop_dong(phong=None):
    with get_conn() as c:
        if phong:
            return c.execute(
                "SELECT * FROM hop_dong WHERE phong_phu_trach=? ORDER BY created_at DESC", (phong,)
            ).fetchall()
        return c.execute("SELECT * FROM hop_dong ORDER BY created_at DESC").fetchall()


def get_hop_dong(ma):
    with get_conn() as c:
        return c.execute("SELECT * FROM hop_dong WHERE ma_hop_dong=?", (ma,)).fetchone()


def add_hop_dong(data, user):
    with get_conn() as c:
        c.execute("""INSERT INTO hop_dong
            (ma_hop_dong, khach_hang, cif, don_vi_thu_huong, so_hd, gia_tri_hd,
             ngay_ket_thuc_hd, loai_tu, loai_gia_tri_kt, pct_khau_tru, phong_phu_trach, ghi_chu, created_by)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (data["ma_hop_dong"], data["khach_hang"], data.get("cif"), data.get("don_vi_thu_huong"), data.get("so_hd"),
             data.get("gia_tri_hd"), data["ngay_ket_thuc_hd"],
             data.get("loai_tu", "khau_tru_dot"), data.get("loai_gia_tri_kt", "Trước VAT"),
             data.get("pct_khau_tru", 10.0), data.get("phong_phu_trach"), data.get("ghi_chu"), user))
        c.commit()
        log(c, "ADD_HOP_DONG", "hop_dong", data["ma_hop_dong"], user, "")


# ---- Tam ung (Giai ngan) ----
def list_tam_ung(ma_hop_dong):
    with get_conn() as c:
        return c.execute("SELECT * FROM tam_ung WHERE ma_hop_dong=? ORDER BY ngay_giai_ngan ASC", (ma_hop_dong,)).fetchall()


def add_tam_ung(data, user):
    with get_conn() as c:
        c.execute("""INSERT INTO tam_ung
            (ma_giai_ngan, ma_hop_dong, so_tien_tu, ngay_giai_ngan, ghi_chu, created_by)
            VALUES (?,?,?,?,?,?)""",
            (data["ma_giai_ngan"], data["ma_hop_dong"], data["so_tien_tu"],
             data["ngay_giai_ngan"], data.get("ghi_chu"), user))
        c.commit()
        log(c, "ADD_GIAI_NGAN", "tam_ung", data["ma_giai_ngan"], user, f"Vào HD {data['ma_hop_dong']}")

def update_tam_ung_ghi_chu(ma_giai_ngan, ghi_chu):
    with get_conn() as c:
        c.execute("UPDATE tam_ung SET ghi_chu=? WHERE ma_giai_ngan=?", (ghi_chu, ma_giai_ngan))
        c.commit()


def delete_hop_dong(ma, user):
    with get_conn() as c:
        # Xóa các bảng con trước để tránh lỗi Foreign Key
        c.execute("DELETE FROM tam_ung WHERE ma_hop_dong=?", (ma,))
        c.execute("DELETE FROM hoa_don WHERE ma_hop_dong=?", (ma,))
        c.execute("DELETE FROM hstt WHERE ma_hop_dong=?", (ma,))
        c.execute("DELETE FROM staging_hd WHERE ma_hop_dong=?", (ma,))
        # Sau đó xóa bảng cha
        c.execute("DELETE FROM hop_dong WHERE ma_hop_dong=?", (ma,))
        c.commit()
        log(c, "DEL_HOP_DONG", "hop_dong", ma, user, "")


# ---- HSTT ----
def list_hstt(ma_hop_dong=None):
    with get_conn() as c:
        if ma_hop_dong:
            return c.execute("SELECT * FROM hstt WHERE ma_hop_dong=? ORDER BY dot_so", (ma_hop_dong,)).fetchall()
        return c.execute("SELECT * FROM hstt ORDER BY ma_hop_dong, dot_so").fetchall()


def add_hstt(data, user):
    with get_conn() as c:
        c.execute("""INSERT INTO hstt
            (ma_hop_dong, dot_so, ngay_hstt, kl_truoc_vat, vat, tong_cong, loai_kl, ghi_chu, created_by)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (data["ma_hop_dong"], data["dot_so"], data["ngay_hstt"],
             data["kl_truoc_vat"], data.get("vat", 0), data.get("tong_cong", data["kl_truoc_vat"]),
             data.get("loai_kl", "Trước VAT"), data.get("ghi_chu"), user))
        c.commit()
        log(c, "ADD_HSTT", "hstt", f"{data['ma_hop_dong']}/dot{data['dot_so']}", user, "")

def update_hstt(hstt_id, data, user):
    with get_conn() as c:
        c.execute("""UPDATE hstt
            SET dot_so=?, ngay_hstt=?, kl_truoc_vat=?, vat=?, tong_cong=?, ghi_chu=?, loai_kl=?
            WHERE id=?""",
            (data["dot_so"], data["ngay_hstt"], data["kl_truoc_vat"], data.get("vat", 0),
             data.get("tong_cong", data["kl_truoc_vat"]), data.get("ghi_chu"), data.get("loai_kl", "Trước VAT"), hstt_id))
        c.commit()
        log(c, "UPDATE_HSTT", "hstt", str(hstt_id), user, "")

def delete_hstt(hstt_id, user):
    with get_conn() as c:
        c.execute("DELETE FROM hstt WHERE id=?", (hstt_id,))
        c.commit()
        log(c, "DELETE_HSTT", "hstt", str(hstt_id), user, "")


# ---- Hoa don ----
def list_hoa_don(ma_hop_dong=None, dot=None, status=None):
    q = "SELECT * FROM hoa_don WHERE 1=1"
    args = []
    if ma_hop_dong: q += " AND ma_hop_dong=?"; args.append(ma_hop_dong)
    if dot is not None: q += " AND dot_so=?"; args.append(dot)
    if status: q += " AND status=?"; args.append(status)
    q += " ORDER BY uploaded_at DESC"
    with get_conn() as c:
        return c.execute(q, args).fetchall()


def add_hoa_don(data, user, status="approved"):
    with get_conn() as c:
        c.execute("""INSERT INTO hoa_don
            (ma_hop_dong, dot_so, so_hd, ngay_hd, mst_ban, ten_ban,
             tien_truoc_vat, vat, tong_cong, ma_tra_cuu, file_src,
             status, uploaded_by, approved_by, approved_at, ghi_chu)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (data["ma_hop_dong"], data.get("dot_so", 1), data["so_hd"], data["ngay_hd"],
             data.get("mst_ban"), data.get("ten_ban"),
             data["tien_truoc_vat"], data["vat"], data.get("tong_cong"),
             data.get("ma_tra_cuu"), data.get("file_src"),
             status, user,
             user if status == "approved" else None,
             datetime.now() if status == "approved" else None,
             data.get("ghi_chu")))
        c.commit()
        log(c, "ADD_HOA_DON", "hoa_don", data["so_hd"], user, "")


def approve_hoa_don(hd_id, user):
    with get_conn() as c:
        c.execute("UPDATE hoa_don SET status='approved', approved_by=?, approved_at=? WHERE id=?",
                  (user, datetime.now(), hd_id))
        c.commit()


def reject_hoa_don(hd_id, user, reason=""):
    with get_conn() as c:
        c.execute("UPDATE hoa_don SET status='rejected', approved_by=?, approved_at=?, ghi_chu=? WHERE id=?",
                  (user, datetime.now(), reason, hd_id))
        c.commit()


# ---- Staging ----
def add_staging(data, user):
    with get_conn() as c:
        cur = c.execute("""INSERT INTO staging_hd 
            (ma_hop_dong, dot_so, so_hd, ngay_hd, mst_ban, ten_ban, tien_truoc_vat, vat, tong_cong,
             ma_tra_cuu, file_src, parse_status, uploaded_by)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (data.get("ma_hop_dong"), data.get("dot_so"), data.get("so_hd"), data.get("ngay_hd"), data.get("mst_ban"),
             data.get("ten_ban"), data.get("tien_truoc_vat"), data.get("vat"),
             data.get("tong_cong"), data.get("ma_tra_cuu"),
             data.get("file_src"), data.get("parse_status"), user))
        c.commit()
        return cur.lastrowid


def list_staging(user=None):
    with get_conn() as c:
        if user:
            return c.execute("SELECT * FROM staging_hd WHERE uploaded_by=? ORDER BY uploaded_at DESC", (user,)).fetchall()
        return c.execute("SELECT * FROM staging_hd ORDER BY uploaded_at DESC").fetchall()


def delete_staging(staging_id):
    with get_conn() as c:
        c.execute("DELETE FROM staging_hd WHERE id=?", (staging_id,))
        c.commit()


def delete_hoa_don(hd_id, user):
    with get_conn() as c:
        c.execute("DELETE FROM hoa_don WHERE id=?", (hd_id,))
        c.commit()


def get_staging(staging_id):
    with get_conn() as c:
        return c.execute("SELECT * FROM staging_hd WHERE id=?", (staging_id,)).fetchone()


# ---- Calc helpers ----
def calc_summary(ma_hop_dong):
    """Tinh luy ke giai ngan, khau tru, HD bo sung, du can bo sung cho 1 Hop Dong."""
    with get_conn() as c:
        hd = c.execute("SELECT * FROM hop_dong WHERE ma_hop_dong=?", (ma_hop_dong,)).fetchone()
        if not hd: return None
        
        # Tong tien da giai ngan cho HD nay
        gn_row = c.execute(
            "SELECT COALESCE(SUM(so_tien_tu), 0), MIN(ngay_giai_ngan) FROM tam_ung WHERE ma_hop_dong=?",
            (ma_hop_dong,)
        ).fetchone()
        tong_giai_ngan = gn_row[0]
        ngay_gn_dau = gn_row[1]
        
        pct = (hd["pct_khau_tru"] or 0) / 100.0
        loai_kt = hd["loai_gia_tri_kt"] if hd["loai_gia_tri_kt"] else "Trước VAT"
        if loai_kt == "Sau VAT":
            kt_luy_ke = c.execute(
                "SELECT COALESCE(SUM(COALESCE(tong_cong, kl_truoc_vat) * ?),0) FROM hstt WHERE ma_hop_dong=?",
                (pct, ma_hop_dong)
            ).fetchone()[0]
        else:
            kt_luy_ke = c.execute(
                "SELECT COALESCE(SUM(kl_truoc_vat * ?),0) FROM hstt WHERE ma_hop_dong=?",
                (pct, ma_hop_dong)
            ).fetchone()[0]
        
        hd_pct = 1.0 if hd["loai_tu"] == "mot_lan" else pct
        hd_loai_kt = "Trước VAT" if hd["loai_tu"] == "mot_lan" else loai_kt
        
        if hd_loai_kt == "Sau VAT":
            hd_luy_ke = c.execute(
                "SELECT COALESCE(SUM(COALESCE(tong_cong, tien_truoc_vat) * ?),0) FROM hoa_don WHERE ma_hop_dong=? AND status='approved'",
                (hd_pct, ma_hop_dong)
            ).fetchone()[0]
        else:
            hd_luy_ke = c.execute(
                "SELECT COALESCE(SUM(tien_truoc_vat * ?),0) FROM hoa_don WHERE ma_hop_dong=? AND status='approved'",
                (hd_pct, ma_hop_dong)
            ).fetchone()[0]
        
        du = max(tong_giai_ngan - hd_luy_ke, 0)
        pct_done = hd_luy_ke / tong_giai_ngan if tong_giai_ngan > 0 else 0
        
        return {
            "tong_giai_ngan": tong_giai_ngan,
            "ngay_giai_ngan_dau": ngay_gn_dau,
            "loai_tu": hd["loai_tu"],
            "khau_tru_luy_ke": kt_luy_ke,
            "hd_luy_ke": hd_luy_ke,
            "du_can_bo_sung": du,
            "pct_hoan_thanh": pct_done,
        }


# ---- Audit ----
def log(conn, action, entity, entity_id, username, details):
    conn.execute(
        "INSERT INTO audit_log (action, entity, entity_id, username, details) VALUES (?,?,?,?,?)",
        (action, entity, entity_id, username, details)
    )

def recent_audit(limit=50):
    with get_conn() as c:
        return c.execute("SELECT * FROM audit_log ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
