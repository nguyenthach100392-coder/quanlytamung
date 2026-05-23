# -*- coding: utf-8 -*-
"""SQLite database layer cho he thong theo doi tam ung."""
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
    """Khoi tao schema neu chua co."""
    conn = get_conn()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
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

    CREATE TABLE IF NOT EXISTS tam_ung (
        ma_giai_ngan TEXT PRIMARY KEY,
        khach_hang TEXT NOT NULL,
        don_vi_thu_huong TEXT,
        so_hd TEXT,
        gia_tri_hd REAL,
        so_tien_tu REAL NOT NULL,
        ngay_giai_ngan DATE NOT NULL,
        ngay_ket_thuc_hd DATE NOT NULL,
        loai_tu TEXT NOT NULL DEFAULT 'khau_tru_dot',
        pct_khau_tru REAL DEFAULT 0.1,
        phong_phu_trach TEXT,
        ghi_chu TEXT,
        created_by TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS hstt (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ma_giai_ngan TEXT NOT NULL,
        dot_so INTEGER NOT NULL,
        ngay_hstt DATE NOT NULL,
        kl_truoc_vat REAL NOT NULL,
        ghi_chu TEXT,
        created_by TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (ma_giai_ngan) REFERENCES tam_ung(ma_giai_ngan),
        UNIQUE(ma_giai_ngan, dot_so)
    );

    CREATE TABLE IF NOT EXISTS hoa_don (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ma_giai_ngan TEXT NOT NULL,
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
        FOREIGN KEY (ma_giai_ngan) REFERENCES tam_ung(ma_giai_ngan)
    );

    CREATE TABLE IF NOT EXISTS staging_hd (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ma_giai_ngan TEXT,
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

    # Migration: add loai_tu column if not exists (for existing DBs)
    try:
        c.execute("SELECT loai_tu FROM tam_ung LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE tam_ung ADD COLUMN loai_tu TEXT NOT NULL DEFAULT 'khau_tru_dot'")
    except: pass
    
    try:
        c.execute("ALTER TABLE tam_ung ADD COLUMN don_vi_thu_huong TEXT")
    except: pass

    # Seed default users
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        c.executemany(
            "INSERT INTO users (username, full_name, dept, role) VALUES (?,?,?,?)",
            [
                ("admin", "Quan tri he thong", "QTTD", "admin"),
                ("qttd01", "Can bo QTTD 01", "QTTD", "qttd"),
                ("phongkh_dn", "Phong KHDN", "KHDN", "phong_kh"),
                ("phongkh_sme", "Phong KH SME", "SME", "phong_kh"),
            ]
        )
    conn.commit()
    conn.close()


# ---- Company name normalization ----
def normalize_company_name(name):
    """Chuan hoa ten cong ty de so sanh: bo tien to, loai hinh, uppercase, trim."""
    s = name.strip().upper()
    # Remove common prefixes in order of specificity (longest first)
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
    # Also strip business type keywords that may remain after prefix removal
    for kw in ['TNHH MTV', 'TNHH', 'CO PHAN', 'CP', 'MTV']:
        s = re.sub(r'\b' + kw + r'\b', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def list_distinct_companies():
    """Lay danh sach ten cong ty da co (distinct) tu khach hang, don vi thu huong, ten nguoi ban."""
    with get_conn() as c:
        rows = c.execute("""
            SELECT khach_hang FROM tam_ung WHERE khach_hang IS NOT NULL AND khach_hang != ''
            UNION
            SELECT don_vi_thu_huong FROM tam_ung WHERE don_vi_thu_huong IS NOT NULL AND don_vi_thu_huong != ''
            UNION
            SELECT ten_ban FROM hoa_don WHERE ten_ban IS NOT NULL AND ten_ban != ''
            ORDER BY 1
        """).fetchall()
        return [r[0] for r in rows]


def find_similar_company(name):
    """Tim cong ty co ten tuong tu (da chuan hoa) trong registry."""
    normalized = normalize_company_name(name)
    with get_conn() as c:
        row = c.execute(
            "SELECT company_name FROM company_registry WHERE normalized_name=? ORDER BY id DESC LIMIT 1",
            (normalized,)
        ).fetchone()
        return row[0] if row else None


def generate_ma_giai_ngan(khach_hang, year=None):
    """Tu sinh ma giai ngan: TU-YYYY-NNN.XX
    NNN = so thu tu cong ty trong nam
    XX  = lan tam ung thu may cua cong ty do trong nam
    """
    if year is None:
        year = date.today().year
    normalized = normalize_company_name(khach_hang)

    conn = get_conn()
    try:
        c = conn.cursor()
        # Check if company already exists in registry for this year
        existing = c.execute(
            "SELECT * FROM company_registry WHERE normalized_name=? AND year=?",
            (normalized, year)
        ).fetchone()

        if existing:
            company_seq = existing['company_seq']
        else:
            # Get next company seq for this year
            max_seq = c.execute(
                "SELECT COALESCE(MAX(company_seq), 0) FROM company_registry WHERE year=?",
                (year,)
            ).fetchone()[0]
            company_seq = max_seq + 1
            c.execute(
                "INSERT INTO company_registry (company_name, normalized_name, company_seq, year) VALUES (?,?,?,?)",
                (khach_hang.strip(), normalized, company_seq, year)
            )

        # Count existing TU for this company in this year
        pattern = f"TU-{year}-{company_seq:03d}.%"
        count = c.execute(
            "SELECT COUNT(*) FROM tam_ung WHERE ma_giai_ngan LIKE ?",
            (pattern,)
        ).fetchone()[0]
        tu_seq = count + 1

        ma = f"TU-{year}-{company_seq:03d}.{tu_seq:02d}"
        conn.commit()
        return ma
    finally:
        conn.close()


# ---- Users ----
def list_users():
    with get_conn() as c:
        return c.execute("SELECT * FROM users WHERE active=1 ORDER BY role, full_name").fetchall()


def get_user(username):
    with get_conn() as c:
        return c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()


# ---- Tam ung ----
def list_tam_ung(phong=None):
    with get_conn() as c:
        if phong:
            return c.execute(
                "SELECT * FROM tam_ung WHERE phong_phu_trach=? ORDER BY ngay_giai_ngan DESC", (phong,)
            ).fetchall()
        return c.execute("SELECT * FROM tam_ung ORDER BY ngay_giai_ngan DESC").fetchall()


def get_tam_ung(ma):
    with get_conn() as c:
        return c.execute("SELECT * FROM tam_ung WHERE ma_giai_ngan=?", (ma,)).fetchone()


def add_tam_ung(data, user):
    with get_conn() as c:
        c.execute("""INSERT INTO tam_ung
            (ma_giai_ngan, khach_hang, don_vi_thu_huong, so_hd, gia_tri_hd, so_tien_tu,
             ngay_giai_ngan, ngay_ket_thuc_hd, loai_tu, pct_khau_tru,
             phong_phu_trach, ghi_chu, created_by)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (data["ma_giai_ngan"], data["khach_hang"], data.get("don_vi_thu_huong"), data.get("so_hd"),
             data.get("gia_tri_hd"), data["so_tien_tu"],
             data["ngay_giai_ngan"], data["ngay_ket_thuc_hd"],
             data.get("loai_tu", "khau_tru_dot"),
             data.get("pct_khau_tru", 0.1),
             data.get("phong_phu_trach"),
             data.get("ghi_chu"), user))
        c.commit()
        log(c, "ADD_TAM_UNG", "tam_ung", data["ma_giai_ngan"], user, str(data))


def delete_tam_ung(ma, user):
    with get_conn() as c:
        c.execute("DELETE FROM tam_ung WHERE ma_giai_ngan=?", (ma,))
        c.commit()
        log(c, "DEL_TAM_UNG", "tam_ung", ma, user, "")


# ---- HSTT ----
def list_hstt(ma_tu=None):
    with get_conn() as c:
        if ma_tu:
            return c.execute(
                "SELECT * FROM hstt WHERE ma_giai_ngan=? ORDER BY dot_so", (ma_tu,)
            ).fetchall()
        return c.execute("SELECT * FROM hstt ORDER BY ma_giai_ngan, dot_so").fetchall()


def add_hstt(data, user):
    with get_conn() as c:
        c.execute("""INSERT INTO hstt
            (ma_giai_ngan, dot_so, ngay_hstt, kl_truoc_vat, ghi_chu, created_by)
            VALUES (?,?,?,?,?,?)""",
            (data["ma_giai_ngan"], data["dot_so"], data["ngay_hstt"],
             data["kl_truoc_vat"], data.get("ghi_chu"), user))
        c.commit()
        log(c, "ADD_HSTT", "hstt", f"{data['ma_giai_ngan']}/dot{data['dot_so']}", user, str(data))


# ---- Hoa don ----
def list_hoa_don(ma_tu=None, dot=None, status=None):
    q = "SELECT * FROM hoa_don WHERE 1=1"
    args = []
    if ma_tu: q += " AND ma_giai_ngan=?"; args.append(ma_tu)
    if dot is not None: q += " AND dot_so=?"; args.append(dot)
    if status: q += " AND status=?"; args.append(status)
    q += " ORDER BY uploaded_at DESC"
    with get_conn() as c:
        return c.execute(q, args).fetchall()


def add_hoa_don(data, user, status="approved"):
    with get_conn() as c:
        c.execute("""INSERT INTO hoa_don
            (ma_giai_ngan, dot_so, so_hd, ngay_hd, mst_ban, ten_ban,
             tien_truoc_vat, vat, tong_cong, ma_tra_cuu, file_src,
             status, uploaded_by, approved_by, approved_at, ghi_chu)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (data["ma_giai_ngan"], data.get("dot_so", 1), data["so_hd"], data["ngay_hd"],
             data.get("mst_ban"), data.get("ten_ban"),
             data["tien_truoc_vat"], data["vat"], data.get("tong_cong"),
             data.get("ma_tra_cuu"), data.get("file_src"),
             status, user,
             user if status == "approved" else None,
             datetime.now() if status == "approved" else None,
             data.get("ghi_chu")))
        c.commit()
        log(c, "ADD_HOA_DON", "hoa_don", data["so_hd"], user, str(data))


def approve_hoa_don(hd_id, user):
    with get_conn() as c:
        c.execute("UPDATE hoa_don SET status='approved', approved_by=?, approved_at=? WHERE id=?",
                  (user, datetime.now(), hd_id))
        c.commit()
        log(c, "APPROVE_HOA_DON", "hoa_don", str(hd_id), user, "")


def reject_hoa_don(hd_id, user, reason=""):
    with get_conn() as c:
        c.execute("UPDATE hoa_don SET status='rejected', approved_by=?, approved_at=?, ghi_chu=? WHERE id=?",
                  (user, datetime.now(), reason, hd_id))
        c.commit()
        log(c, "REJECT_HOA_DON", "hoa_don", str(hd_id), user, reason)


# ---- Staging ----
def add_staging(data, user):
    with get_conn() as c:
        cur = c.execute("""INSERT INTO staging_hd 
            (ma_giai_ngan, dot_so, so_hd, ngay_hd, mst_ban, ten_ban, tien_truoc_vat, vat, tong_cong,
             ma_tra_cuu, file_src, parse_status, uploaded_by)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (data.get("ma_giai_ngan"), data.get("dot_so"), data.get("so_hd"), data.get("ngay_hd"), data.get("mst_ban"),
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


def update_staging_assignment(staging_id, ma_tu, dot):
    with get_conn() as c:
        c.execute("UPDATE staging_hd SET ma_giai_ngan=?, dot_so=? WHERE id=?",
                  (ma_tu, dot, staging_id))
        c.commit()


def delete_staging(staging_id):
    with get_conn() as c:
        c.execute("DELETE FROM staging_hd WHERE id=?", (staging_id,))
        c.commit()


def delete_hoa_don(hd_id, user):
    with get_conn() as c:
        c.execute("DELETE FROM hoa_don WHERE id=?", (hd_id,))
        log(c, "DELETE", "hoa_don", hd_id, user, f"Xoa HD ID {hd_id}")
        c.commit()


def get_staging(staging_id):
    with get_conn() as c:
        return c.execute("SELECT * FROM staging_hd WHERE id=?", (staging_id,)).fetchone()


# ---- Calc helpers ----
def calc_summary(ma_tu):
    """Tinh luy ke khau tru, HD bo sung, du can bo sung cho mot mon."""
    with get_conn() as c:
        tu = c.execute("SELECT * FROM tam_ung WHERE ma_giai_ngan=?", (ma_tu,)).fetchone()
        if not tu: return None
        pct = tu["pct_khau_tru"] or 0
        kt_luy_ke = c.execute(
            "SELECT COALESCE(SUM(kl_truoc_vat * ?),0) FROM hstt WHERE ma_giai_ngan=?",
            (pct, ma_tu)
        ).fetchone()[0]
        hd_luy_ke = c.execute(
            "SELECT COALESCE(SUM(tien_truoc_vat),0) FROM hoa_don WHERE ma_giai_ngan=? AND status='approved'",
            (ma_tu,)
        ).fetchone()[0]
        du = max(tu["so_tien_tu"] - hd_luy_ke, 0)
        pct_done = hd_luy_ke / tu["so_tien_tu"] if tu["so_tien_tu"] else 0
        return {
            "so_tien_tu": tu["so_tien_tu"],
            "loai_tu": tu["loai_tu"],
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
