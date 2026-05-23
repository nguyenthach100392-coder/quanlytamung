# -*- coding: utf-8 -*-
"""
Web app theo doi tam ung & bo sung hoa don
Chay: streamlit run app.py --server.address 0.0.0.0 --server.port 8501
"""
import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
import os
import db
import parsers
import exporter

st.set_page_config(page_title="Theo dõi Tạm ứng & HĐ", layout="wide", page_icon="📊")

# Init DB once
db.init_db()

# ============ AUTH ============
def login_screen():
    st.title("📊 Hệ thống theo dõi Tạm ứng & Bổ sung Hóa đơn")
    st.caption("Đăng nhập để tiếp tục")
    users = db.list_users()
    options = {f"{u['full_name']} ({u['role']} - {u['dept'] or ''})": u['username'] for u in users}
    choice = st.selectbox("Chọn user", list(options.keys()))
    if st.button("Đăng nhập", type="primary"):
        st.session_state["user"] = options[choice]
        st.session_state["user_info"] = dict(db.get_user(options[choice]))
        st.rerun()
    st.info("Demo: chon user de vao. Production: thay bang LDAP/SSO ngan hang.")


if "user" not in st.session_state:
    login_screen()
    st.stop()

user = st.session_state["user"]
uinfo = st.session_state["user_info"]
role = uinfo["role"]
is_qttd = role in ("qttd", "admin")
is_phong_kh = role == "phong_kh"

# ============ SIDEBAR (SIMPLIFIED) ============
with st.sidebar:
    st.markdown(f"### 👤 {uinfo['full_name']}")
    st.caption(f"Role: **{role.upper()}** | Phòng: {uinfo['dept'] or '-'}")
    if st.button("Đăng xuất"):
        del st.session_state["user"]
        st.rerun()
    st.divider()

    if is_qttd:
        page = st.radio("Menu", [
            "📊 Dashboard",
            "➕ Thêm món tạm ứng mới",
            "💰 Quản lý Tạm ứng",
            "✅ Duyệt HĐ chờ",
            "📦 Export & Drive",
            "🗂 Audit log",
        ])
    else:
        page = st.radio("Menu", [
            "📊 Dashboard (Của phòng)",
            "➕ Thêm món tạm ứng mới",
            "💰 Danh sách Tạm ứng",
        ])


# ============ HELPERS ============
def fmt_vnd(x):
    if x is None: return "-"
    try: return f"{float(x):,.0f}"
    except: return str(x)


def fmt_vnd_dot(x):
    """Format so tien voi dau cham ngan: 500.000.000"""
    if x is None or x == 0: return ""
    try: return f"{int(float(x)):,}".replace(",", ".")
    except: return str(x)


def parse_vnd_input(text):
    """Parse VND input: '500000000' hoac '500.000.000' -> float"""
    if not text: return None
    text = str(text).strip().replace(" ", "").replace(".", "").replace(",", "")
    try: return float(text)
    except: return None


def fmt_date(d):
    """Format date -> dd/mm/yyyy"""
    if isinstance(d, str):
        try: d = datetime.strptime(d, "%Y-%m-%d").date()
        except: return d
    if isinstance(d, date): return d.strftime("%d/%m/%Y")
    return str(d) if d else "-"


def status_badge(s):
    colors = {"Hoàn tất": "green", "Quá hạn": "red", "Sắp đến hạn": "orange",
              "Đang theo dõi": "blue", "Du HD": "green", "Tre han": "red",
              "Dang cho HD": "orange", "approved": "green", "pending": "orange", "rejected": "red"}
    return f":{colors.get(s, 'gray')}[**{s}**]"


def compute_tu_status(r):
    today = date.today()
    summary = db.calc_summary(r["ma_giai_ngan"])
    if not summary: return summary, "?"
    nkt = r["ngay_ket_thuc_hd"]
    if isinstance(nkt, str):
        nkt = datetime.strptime(nkt, "%Y-%m-%d").date()
    han_cuoi = nkt - timedelta(days=30)
    if summary["hd_luy_ke"] >= r["so_tien_tu"]: tt = "Hoàn tất"
    elif today > han_cuoi: tt = "Quá hạn"
    elif (han_cuoi - today).days <= 15: tt = "Sắp đến hạn"
    else: tt = "Đang theo dõi"
    
    summary["han_cuoi"] = han_cuoi
    return summary, tt


# ============ PAGE: DASHBOARD ============
def page_dashboard():
    st.title("📊 Dashboard")
    phong = uinfo["dept"] if is_phong_kh else None
    tu_list = db.list_tam_ung(phong=phong)

    # --- Filters ---
    kh_list = sorted(list(set([r["khach_hang"] for r in tu_list if r["khach_hang"]])))
    dvth_list = sorted(list(set([r["don_vi_thu_huong"] for r in tu_list if 'don_vi_thu_huong' in r.keys() and r["don_vi_thu_huong"]])))
    
    with st.expander("🔍 Lọc dữ liệu", expanded=False):
        c1, c2 = st.columns(2)
        kh_filters = c1.multiselect("Khách hàng", kh_list)
        dvth_filters = c2.multiselect("Đơn vị thụ hưởng", dvth_list)
        
    if kh_filters:
        tu_list = [r for r in tu_list if r["khach_hang"] in kh_filters]
    if dvth_filters:
        tu_list = [r for r in tu_list if 'don_vi_thu_huong' in r.keys() and r["don_vi_thu_huong"] in dvth_filters]

    total_tu = sum(r["so_tien_tu"] for r in tu_list)
    total_hd = 0
    qua_han = sap_han = hoan_tat = 0
    rows_display = []
    for r in tu_list:
        s, tt = compute_tu_status(r)
        total_hd += s["hd_luy_ke"]
        if tt == "Quá hạn": qua_han += 1
        elif tt == "Sắp đến hạn": sap_han += 1
        elif tt == "Hoàn tất": hoan_tat += 1
        loai = r["loai_tu"] if "loai_tu" in r.keys() else "khau_tru_dot"
        rows_display.append({
            "Mã hồ sơ": r["ma_giai_ngan"], "Khách hàng": r["khach_hang"],
            "ĐV thụ hưởng": (r['don_vi_thu_huong'] if 'don_vi_thu_huong' in r.keys() and r['don_vi_thu_huong'] else ""),
            "Loại": "Từng đợt" if loai == "khau_tru_dot" else "1 lần",
            "Phòng": r["phong_phu_trach"] or "",
            "Tạm ứng": s["so_tien_tu"], "HĐ bổ sung": s["hd_luy_ke"],
            "Dư cần bổ sung": s["du_can_bo_sung"],
            "Hạn bổ sung": fmt_date(s["han_cuoi"]),
            "% Hoàn thành": s["pct_hoan_thanh"], "Trạng thái": tt,
        })

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tổng món TU", len(tu_list))
    c2.metric("Giá trị TU (tr)", f"{total_tu/1e6:,.0f}")
    c3.metric("Đã bổ sung HĐ (tr)", f"{total_hd/1e6:,.0f}")
    c4.metric("Tỷ lệ bổ sung", f"{(total_hd/total_tu*100 if total_tu else 0):.1f}%")

    c1, c2, c3 = st.columns(3)
    c1.metric("🔴 Quá hạn", qua_han)
    c2.metric("🟡 Sắp đến hạn", sap_han)
    c3.metric("🟢 Hoàn tất", hoan_tat)

    if rows_display:
        df = pd.DataFrame(rows_display)
        df["Tạm ứng"] = df["Tạm ứng"].apply(fmt_vnd)
        df["HĐ bổ sung"] = df["HĐ bổ sung"].apply(fmt_vnd)
        df["Dư cần bổ sung"] = df["Dư cần bổ sung"].apply(fmt_vnd)
        df["% Hoàn thành"] = df["% Hoàn thành"].apply(lambda x: f"{x*100:.1f}%")
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Chua co món tam ung nao.")


# ============ PAGE: QUAN LY TAM UNG (COMBINED) ============
def page_tam_ung():
    st.title("💰 Quản lý Tạm ứng")

    # ------ SEARCH / FILTER BAR ------
    st.subheader("🔍 Tim kiem")
    fc1, fc2, fc3 = st.columns([3, 1, 1])
    search_text = fc1.text_input("Tim theo ten KH, ma ho so, so HD...",
                                 placeholder="VD: ABC, TU-2026-001, HD-2026...",
                                 key="search_tu")
    filter_phong = fc2.selectbox("Phòng", ["Tất cả", "PGD Hàng Xanh", "PGD Đinh Tiên Hoàng", "PGD Đakao", "PGD Nguyễn Oanh", "PGD Tân Thới Hiệp", "KHDN1", "KHDN2", "KH FDI"], key="filter_phong")
    filter_loai = fc3.selectbox("Loại TU", ["Tất cả", "Khấu trừ từng đợt", "Thanh toán 1 lần"], key="filter_loai")

    # Fetch & filter
    phong_filter = None if is_qttd else uinfo["dept"]
    all_rows = db.list_tam_ung(phong=phong_filter)
    filtered = []
    for r in all_rows:
        loai = r["loai_tu"] if "loai_tu" in r.keys() else "khau_tru_dot"
        # Apply phong filter
        if filter_phong != "Tất cả" and r["phong_phu_trach"] != filter_phong:
            continue
        # Apply loai filter
        if filter_loai == "Khấu trừ từng đợt" and loai != "khau_tru_dot":
            continue
        if filter_loai == "Thanh toán 1 lần" and loai != "mot_lan":
            continue
        # Apply text search
        if search_text:
            q = search_text.strip().upper()
            so_hd = r['so_hd'] if r['so_hd'] else ''
            gc = r['ghi_chu'] if r['ghi_chu'] else ''
            dvth = r['don_vi_thu_huong'] if 'don_vi_thu_huong' in r.keys() and r['don_vi_thu_huong'] else ''
            searchable = f"{r['ma_giai_ngan']} {r['khach_hang']} {dvth} {so_hd} {gc}".upper()
            if q not in searchable:
                continue
        filtered.append(r)

    st.caption(f"Hiển thị {len(filtered)}/{len(all_rows)} món")

    # ------ TABLE DISPLAY ------
    if not filtered:
        st.info("Không tìm thấy món tạm ứng nào phù hợp.")
    else:
        # Build display table with radio selection
        table_data = []
        ma_list = []
        for r in filtered:
            s, tt = compute_tu_status(r)
            loai = r["loai_tu"] if "loai_tu" in r.keys() else "khau_tru_dot"
            ma_list.append(r["ma_giai_ngan"])
            table_data.append({
                "Mã hồ sơ": r["ma_giai_ngan"],
                "Khách hàng": r["khach_hang"],
                "ĐV thụ hưởng": (r['don_vi_thu_huong'] if 'don_vi_thu_huong' in r.keys() and r['don_vi_thu_huong'] else ""),
                "Loại": "Từng đợt" if loai == "khau_tru_dot" else "1 lần",
                "Số HĐ": r["so_hd"] if r["so_hd"] else "-",
                "Phòng": r["phong_phu_trach"] or "",
                "Tạm ứng": fmt_vnd(r["so_tien_tu"]),
                "Đã bổ sung": fmt_vnd(s["hd_luy_ke"]),
                "Còn lại": fmt_vnd(s["du_can_bo_sung"]),
                "Ngày GN": fmt_date(r["ngay_giai_ngan"]),
                "Trạng thái": tt,
            })
        st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)

        # ------ SELECT & MANAGE ------
        st.divider()
        selected_idx = st.selectbox(
            "📌 Chọn món tạm ứng để thao tác:",
            range(len(filtered)),
            format_func=lambda i: f"{filtered[i]['ma_giai_ngan']} - {filtered[i]['khach_hang']} ({fmt_vnd(filtered[i]['so_tien_tu'])} VND)" + (f" - ĐVTH: {filtered[i]['don_vi_thu_huong']}" if 'don_vi_thu_huong' in filtered[i].keys() and filtered[i]['don_vi_thu_huong'] else ""),
            key="select_tu"
        )
        selected = filtered[selected_idx]
        s, tt = compute_tu_status(selected)
        loai = selected["loai_tu"] if "loai_tu" in selected.keys() else "khau_tru_dot"

        # ------ DETAIL & ACTIONS TABS ------
        if loai == "khau_tru_dot":
            tab_names = ["📄 Chi tiet", "📋 HSTT", "📤 Bo sung HD", "🧾 DS Hoa don"]
        else:
            tab_names = ["📄 Chi tiet", "📤 Bo sung HD", "🧾 DS Hoa don"]
        tabs = st.tabs(tab_names)

        # --- TAB: Chi tiet ---
        with tabs[0]:
            st.markdown(f"#### Thông tin chung")
            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(f"**Mã hồ sơ:** `{selected['ma_giai_ngan']}`")
            c2.markdown(f"**Khách hàng:** {selected['khach_hang']}")
            c3.markdown(f"**Trạng thái:** {status_badge(tt)}")
            c4.markdown(f"**Loại:** {'Khấu trừ từng đợt' if loai == 'khau_tru_dot' else 'Thanh toán 1 lần'}")

            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(f"**Số HĐ:** {selected['so_hd'] if selected['so_hd'] else '-'}")
            c2.markdown(f"**ĐV thụ hưởng:** {selected['don_vi_thu_huong'] if 'don_vi_thu_huong' in selected.keys() and selected['don_vi_thu_huong'] else '-'}")
            c3.markdown(f"**Ngày GN:** {fmt_date(selected['ngay_giai_ngan'])}")
            c4.markdown(f"**Ngày KT HĐ:** {fmt_date(selected['ngay_ket_thuc_hd'])}")
            if loai == "khau_tru_dot":
                st.markdown(f"**% Khấu trừ/đợt:** {selected['pct_khau_tru']*100:.0f}%")

            if selected["ghi_chu"]:
                st.markdown(f"**Ghi chú:** {selected['ghi_chu']}")

            st.divider()
            st.markdown(f"#### Số liệu tài chính")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Giá trị HĐ", fmt_vnd_dot(selected["gia_tri_hd"]) + " ₫" if selected["gia_tri_hd"] else "-")
            c2.metric("Tạm ứng", fmt_vnd_dot(selected["so_tien_tu"]) + " ₫")
            c3.metric("Đã bổ sung HĐ", fmt_vnd_dot(s["hd_luy_ke"]) + " ₫")
            c4.metric("Còn phải bổ sung", fmt_vnd_dot(s["du_can_bo_sung"]) + " ₫")

            # Progress bar
            pct_done = s["pct_hoan_thanh"]
            st.progress(min(pct_done, 1.0), text=f"Hoan thanh: {pct_done*100:.1f}%")

        # --- TAB: HSTT (only for khau_tru_dot) ---
        tab_offset = 0
        if loai == "khau_tru_dot":
            with tabs[1]:
                hstt_rows = db.list_hstt(selected["ma_giai_ngan"])
                if hstt_rows:
                    data = []
                    for r in hstt_rows:
                        kt = r["kl_truoc_vat"] * selected["pct_khau_tru"]
                        data.append({
                            "Dot": r["dot_so"],
                            "Ngay HSTT": fmt_date(r["ngay_hstt"]),
                            "KL truoc VAT": fmt_vnd(r["kl_truoc_vat"]),
                            "Khau tru TU": fmt_vnd(kt),
                            "Han bo sung HD": fmt_date(r["ngay_hstt"] + timedelta(days=15)) if isinstance(r["ngay_hstt"], date) else "-",
                            "Ghi chú": r["ghi_chu"] or "",
                        })
                    st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
                else:
                    st.info("Chua co HSTT nao.")

                with st.expander("➕ Thêm dot HSTT moi"):
                    with st.form(f"hstt_{selected['ma_giai_ngan']}"):
                        next_dot = max([r["dot_so"] for r in hstt_rows], default=0) + 1
                        c1, c2 = st.columns(2)
                        dot = c1.number_input("Dot #", min_value=1, value=next_dot)
                        ngay = c2.date_input("Ngay HSTT", value=date.today(), format="DD/MM/YYYY")
                        kl_text = st.text_input("KL truoc VAT (VND)", placeholder="VD: 1.000.000.000")
                        ghi_chu = st.text_input("Ghi chú")
                        kl = parse_vnd_input(kl_text)
                        if kl:
                            st.caption(f"= {fmt_vnd_dot(kl)} VND → Khau tru: {fmt_vnd_dot(kl * selected['pct_khau_tru'])} VND")
                        if st.form_submit_button("Thêm HSTT", type="primary"):
                            if not kl or kl <= 0:
                                st.error("Nhap KL truoc VAT hop le!")
                            else:
                                try:
                                    db.add_hstt({"ma_giai_ngan": selected["ma_giai_ngan"], "dot_so": int(dot),
                                                 "ngay_hstt": ngay, "kl_truoc_vat": kl, "ghi_chu": ghi_chu}, user)
                                    st.success(f"Da them HSTT dot {dot}")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Lỗi: {e}")
            tab_offset = 1

        # --- TAB: Bo sung HD ---
        with tabs[1 + tab_offset]:
            st.subheader("Upload hóa đơn bổ sung")
            if loai == "mot_lan":
                st.info("📌 Loai thanh toan 1 lan - chi can xuat 1 hoa don khi nhan hang.")

            files = st.file_uploader("Chọn file XML/PDF hóa đơn", accept_multiple_files=True,
                                     type=["xml", "pdf"], key=f"upload_{selected['ma_giai_ngan']}")

            if loai == "khau_tru_dot":
                hstt_list = db.list_hstt(selected["ma_giai_ngan"])
                max_dot = max([r["dot_so"] for r in hstt_list], default=1)
                dot_sel = st.number_input("Gán vào đợt #", min_value=1, value=max_dot, step=1, key=f"dot_{selected['ma_giai_ngan']}")
            else:
                dot_sel = 1

            if files and st.button("📥 Trích xuất file", key=f"save_{selected['ma_giai_ngan']}"):
                ok = 0
                for f in files:
                    d = parsers.parse_file(f)
                    d["ma_giai_ngan"] = selected["ma_giai_ngan"]
                    d["dot_so"] = int(dot_sel)
                    db.add_staging(d, user)
                    ok += 1
                st.success(f"✅ Đã trích xuất {ok} file. Vui lòng kiểm tra và bấm Xác nhận ở bên dưới!")
                st.rerun()

            # Hiển thị các hóa đơn vừa upload (từ staging)
            stagings = db.list_staging(user=user if is_phong_kh else None)
            tu_stagings = [s for s in stagings if s["ma_giai_ngan"] == selected["ma_giai_ngan"]]
            if tu_stagings:
                st.markdown("##### 📝 Hóa đơn vừa tải lên (Chờ xác nhận)")
                for s in tu_stagings:
                    so_hd_disp = s['so_hd'] if s['so_hd'] else 'Chưa rõ'
                    file_src_disp = s['file_src'] if s['file_src'] else ''
                    with st.expander(f"HĐ: {so_hd_disp} - {file_src_disp}", expanded=True):
                        with st.form(f"confirm_{s['id']}"):
                            c1, c2 = st.columns(2)
                            so_hd = c1.text_input("Số hóa đơn *", value=s['so_hd'] if s['so_hd'] else "")
                            
                            def_date = date.today()
                            if s['ngay_hd']:
                                try:
                                    if isinstance(s["ngay_hd"], str):
                                        def_date = datetime.strptime(s["ngay_hd"], "%Y-%m-%d").date()
                                    else:
                                        def_date = s["ngay_hd"]
                                except: pass
                            ngay_hd = c2.date_input("Ngày hóa đơn", value=def_date, format="DD/MM/YYYY")
                            
                            c1, c2 = st.columns(2)
                            ten_ban = c1.text_input("Tên người bán", value=s['ten_ban'] if s['ten_ban'] else "")
                            mst = c2.text_input("MST người bán", value=s['mst_ban'] if s['mst_ban'] else "")
                            
                            dvth_tu = selected['don_vi_thu_huong'] if 'don_vi_thu_huong' in selected.keys() and selected['don_vi_thu_huong'] else None
                            if dvth_tu and ten_ban:
                                norm_dvth = db.normalize_company_name(dvth_tu)
                                norm_tb = db.normalize_company_name(ten_ban)
                                if norm_dvth and norm_tb and norm_dvth != norm_tb:
                                    st.warning(f"⚠️ **Cảnh báo:** Tên người bán trên HĐ không khớp Đơn vị thụ hưởng ({dvth_tu}) của Món tạm ứng!")
                                elif norm_dvth and norm_tb and norm_dvth == norm_tb:
                                    st.success(f"✅ Tên người bán khớp với Đơn vị thụ hưởng ({dvth_tu})")
                            
                            c1, c2 = st.columns(2)
                            tien_val = f"{int(s['tien_truoc_vat'])}" if s['tien_truoc_vat'] else ""
                            vat_val = f"{int(s['vat'])}" if s['vat'] else ""
                            tien_text = c1.text_input("Tiền trước VAT (VND) *", value=tien_val, placeholder="VD: 50000000")
                            vat_text = c2.text_input("Tiền VAT (VND)", value=vat_val)
                            
                            c1, c2, c3 = st.columns([2, 1, 1])
                            tien = parse_vnd_input(tien_text)
                            vat = parse_vnd_input(vat_text) or 0
                            if tien:
                                c1.caption(f"Trị giá: {fmt_vnd_dot(tien)} | VAT: {fmt_vnd_dot(vat)} | Tổng: {fmt_vnd_dot(tien + vat)}")
                            
                            if c2.form_submit_button("✓ Xác nhận lưu", type="primary"):
                                if not so_hd or not tien:
                                    st.error("Nhập số HĐ và tiền trước VAT!")
                                else:
                                    db.add_hoa_don({
                                        "ma_giai_ngan": selected["ma_giai_ngan"], "dot_so": s["dot_so"],
                                        "so_hd": so_hd, "ngay_hd": ngay_hd,
                                        "mst_ban": mst, "ten_ban": ten_ban,
                                        "tien_truoc_vat": tien, "vat": vat,
                                        "tong_cong": tien + vat, "ma_tra_cuu": s['ma_tra_cuu'] if s['ma_tra_cuu'] else None,
                                        "file_src": s['file_src'] if s['file_src'] else None, "ghi_chu": f"Upload boi {user}"
                                    }, user, status="approved" if is_qttd else "pending")
                                    db.delete_staging(s["id"])
                                    st.success(f"Đã lưu HĐ {so_hd}")
                                    st.rerun()
                            
                            if c3.form_submit_button("🗑️ Xóa file này"):
                                db.delete_staging(s["id"])
                                st.rerun()

            # Manual entry form
            with st.expander("✍️ Nhập thủ công hóa đơn"):
                with st.form(f"manual_hd_{selected['ma_giai_ngan']}"):
                    c1, c2 = st.columns(2)
                    so_hd = c1.text_input("So hoa don *")
                    ngay_hd = c2.date_input("Ngay hoa don", value=date.today(), format="DD/MM/YYYY")
                    ten_ban = c1.text_input("Ten nguoi ban")
                    mst = c2.text_input("MST nguoi ban")
                    tien_text = c1.text_input("Tien truoc VAT *", placeholder="VD: 50.000.000")
                    vat_text = c2.text_input("Tien VAT", placeholder="VD: 5.000.000")
                    tien = parse_vnd_input(tien_text)
                    vat = parse_vnd_input(vat_text) or 0
                    if tien:
                        st.caption(f"Truoc VAT: {fmt_vnd_dot(tien)} | VAT: {fmt_vnd_dot(vat)} | Tong: {fmt_vnd_dot(tien + vat)} VND")
                    if st.form_submit_button("Luu hoa don", type="primary"):
                        if not so_hd or not tien:
                            st.error("Nhap so HD va tien truoc VAT!")
                        else:
                            db.add_hoa_don({
                                "ma_giai_ngan": selected["ma_giai_ngan"], "dot_so": int(dot_sel),
                                "so_hd": so_hd, "ngay_hd": ngay_hd,
                                "mst_ban": mst, "ten_ban": ten_ban,
                                "tien_truoc_vat": tien, "vat": vat,
                                "tong_cong": tien + vat, "file_src": "manual",
                                "ghi_chu": f"Nhap thu cong boi {user}"
                            }, user, status="approved" if is_qttd else "pending")
                            st.success(f"Da luu HD {so_hd}")
                            st.rerun()

        # --- TAB: DS Hoa don ---
        with tabs[2 + tab_offset]:
            hd_list = db.list_hoa_don(ma_tu=selected["ma_giai_ngan"])
            if hd_list:
                for h in hd_list:
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3, 2, 1])
                        c1.markdown(f"**Số HĐ:** {h['so_hd']} | **Ngày:** {fmt_date(h['ngay_hd'])}")
                        c1.caption(f"KH: {h['ten_ban'] or '-'}")
                        c2.markdown(f"**Đợt:** {h['dot_so']} | **TT:** {status_badge(h['status'])}")
                        c2.caption(f"Tiền: {fmt_vnd(h['tien_truoc_vat'])} | VAT: {fmt_vnd(h['vat'])}")
                        if c3.button("🗑️ Xóa", key=f"del_hd_{h['id']}", help="Xóa hóa đơn bị trùng/lỗi"):
                            db.delete_hoa_don(h['id'], user)
                            st.success(f"Đã xóa HĐ {h['so_hd']}")
                            st.rerun()
            else:
                st.info("Chua co hoa don nao cho món nay.")

    
# ============ PAGE: THEM MON TAM UNG MOI ============
def page_them_tam_ung():
    st.title("➕ Thêm món tạm ứng mới")
    loai_tu = st.radio("Loại thanh toán *", [
        "Khấu trừ từng đợt", "Thanh toán 1 lần"
    ], horizontal=True, key="loai_tu_new")
    is_mot_lan = loai_tu == "Thanh toán 1 lần"
    existing_companies = db.list_distinct_companies()

    with st.form("them_tu_new"):
        c1, c2 = st.columns(2)
        if existing_companies:
            kh_options = ["--- Nhập công ty mới ---"] + existing_companies
            kh_select = c1.selectbox("Chọn KH đã có", kh_options)
        else:
            kh_select = "--- Nhập công ty mới ---"
        kh_new = c2.text_input("Hoặc nhập tên mới", help="Hệ thống tự chuẩn hóa tên")
        if kh_new:
            similar = db.find_similar_company(kh_new)
            if similar:
                st.info(f"💡 KH tuong tu: **{similar}**")

        c1, c2 = st.columns(2)
        if existing_companies:
            dv_options = ["--- Nhập mới ---"] + existing_companies
            don_vi_thu_huong = c1.selectbox("Đơn vị thụ hưởng", dv_options)
        else:
            don_vi_thu_huong = "--- Nhập mới ---"
        dvth_new = c2.text_input("Hoặc nhập ĐVTH mới")

        c1, c2 = st.columns(2)
        so_hd = c1.text_input("Số hợp đồng")
        if is_phong_kh:
            phong = uinfo["dept"]
            c2.text_input("Phòng phụ trách", value=phong, disabled=True)
        else:
            phong = c2.selectbox("Phòng phụ trách", ["PGD Hàng Xanh", "PGD Đinh Tiên Hoàng", "PGD Đakao", "PGD Nguyễn Oanh", "PGD Tân Thới Hiệp", "KHDN1", "KHDN2", "KH FDI"])
        gtri_text = c1.text_input("Giá trị HĐ (VND)", placeholder="5.000.000.000")
        tu_text = c2.text_input("Số tiền tạm ứng *", placeholder="500.000.000")
        ngay_gn = c1.date_input("Ngày giải ngân", value=date.today(), format="DD/MM/YYYY")
        ngay_kt = c2.date_input("Ngày kết thúc HĐ", value=date.today() + timedelta(days=180), format="DD/MM/YYYY")
        if not is_mot_lan:
            pct = c1.number_input("% Khau tru/dot", min_value=0.0, max_value=1.0, value=0.1, step=0.01)
        else:
            pct = 0.0
        ghi_chu = st.text_area("Ghi chú")
        gtri = parse_vnd_input(gtri_text)
        tu_amt = parse_vnd_input(tu_text)
        if tu_amt:
            st.caption(f"Tạm ứng: **{fmt_vnd_dot(tu_amt)} VND**")

        if st.form_submit_button("➕ Thêm", type="primary"):
            kh = kh_new.strip() if kh_new.strip() else (kh_select if kh_select != "--- Nhập công ty mới ---" else "")
            dvth = dvth_new.strip() if dvth_new.strip() else (don_vi_thu_huong if don_vi_thu_huong != "--- Nhập mới ---" else "")
            if not kh:
                st.error("Nhập tên khách hàng!")
            elif not tu_amt or tu_amt <= 0:
                st.error("Nhập số tiền tạm ứng!")
            else:
                try:
                    ma = db.generate_ma_giai_ngan(kh)
                    db.add_tam_ung({
                        "ma_giai_ngan": ma, "khach_hang": kh, "don_vi_thu_huong": dvth, "so_hd": so_hd,
                        "gia_tri_hd": gtri, "so_tien_tu": tu_amt,
                        "ngay_giai_ngan": ngay_gn, "ngay_ket_thuc_hd": ngay_kt,
                        "loai_tu": "mot_lan" if is_mot_lan else "khau_tru_dot",
                        "pct_khau_tru": pct, "phong_phu_trach": phong, "ghi_chu": ghi_chu,
                    }, user)
                    st.success(f"✅ Mã hồ sơ: **{ma}**")
                    st.info("💡 Chuyển sang menu 'Danh sách Tạm ứng' để tìm món vừa tạo và bổ sung hóa đơn.")
                    # Allow user to see the message before rerun (streamlit rerun clears messages)
                    # Instead of immediate rerun, we just don't rerun or we sleep.
                    # Since we are not using sleep, let's just let it be. Wait, if we rerun immediately, the success message is cleared!
                    # The original code had st.rerun(). But if it reruns, the form is cleared and messages are lost!
                    # Actually, we can just remove st.rerun() here so the success message stays, and the user can navigate.
                except Exception as e:
                    st.error(f"Lỗi: {e}")


# ============ PAGE: DUYET HD CHO ============
def page_duyet_hd():
    st.title("⏳ Duyệt Hóa đơn chờ")
    pending = db.list_hoa_don(status="pending")
    if not pending:
        st.success("Không có HĐ chờ duyệt.")
        return
    for h in pending:
        with st.container(border=True):
            c1, c2 = st.columns([3, 1])
            c1.write(f"**HD {h['so_hd']}** | {fmt_date(h['ngay_hd'])} | {h['ten_ban'] or '-'}")
            c1.caption(f"Ma TU: {h['ma_giai_ngan']} | Dot: {h['dot_so']} | Tien: {fmt_vnd(h['tien_truoc_vat'])} | VAT: {fmt_vnd(h['vat'])}")
            c1.caption(f"Upload: {h['uploaded_by']} luc {h['uploaded_at']}")
            if c2.button("✓ Duyệt", key=f"app_{h['id']}", type="primary"):
                db.approve_hoa_don(h["id"], user)
                st.rerun()
            reason = c2.text_input("Lý do reject", key=f"rsn_{h['id']}")
            if c2.button("✗ Từ chối", key=f"rej_{h['id']}"):
                db.reject_hoa_don(h["id"], user, reason)
                st.rerun()


# ============ PAGE: EXPORT ============
def page_export():
    st.title("📦 Export Excel & Đẩy lên Google Drive")
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Tải file Excel về máy")
        if st.button("Xuất file Excel", type="primary"):
            out = exporter.export_excel()
            with open(out, "rb") as f:
                data = f.read()
            st.download_button("⬇️ Tải file", data=data,
                               file_name=os.path.basename(out),
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            st.success(f"Đã xuất {out}")

    with c2:
        st.subheader("Đẩy file lên folder Google Drive (sync local)")
        st.caption("Yêu cầu: Đã cài Google Drive Desktop và sync 1 folder.")
        drive_path = st.text_input("Đường dẫn folder Drive local",
                                   value=os.environ.get("DRIVE_FOLDER", "G:/My Drive/TamUng"))
        if st.button("📤 Push lên Drive", type="primary"):
            try:
                dest, latest = exporter.export_to_drive_folder(drive_path)
                st.success(f"Đã push file:\n- {dest}\n- {latest}")
            except Exception as e:
                st.error(f"Lỗi: {e}")


# ============ PAGE: AUDIT ============
def page_audit():
    st.title("🗂 Audit log")
    rows = db.recent_audit(100)
    df = pd.DataFrame([dict(r) for r in rows])
    st.dataframe(df, use_container_width=True, hide_index=True)


# ============ ROUTE ============
if page.startswith("📊 Dashboard"):
    page_dashboard()
elif page == "➕ Thêm món tạm ứng mới":
    page_them_tam_ung()
elif page in ("💰 Quản lý Tạm ứng", "💰 Danh sách Tạm ứng"):
    page_tam_ung()
elif page == "✅ Duyệt HĐ chờ":
    page_duyet_hd()
elif page == "📦 Export & Drive":
    page_export()
elif page == "🗂 Audit log":
    page_audit()

