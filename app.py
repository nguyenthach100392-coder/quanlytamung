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
    
    username = options[choice]
    user_info = dict(db.get_user(username))
    
    password = st.text_input("Mật khẩu", type="password", placeholder="Nhập mật khẩu")
        
    if st.button("Đăng nhập", type="primary"):
        db_pass = user_info.get('password') or "123456"
        if password != db_pass:
            st.error("Mật khẩu không chính xác!")
        else:
            st.session_state["user"] = username
            st.session_state["user_info"] = user_info
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

# ============ SIDEBAR ============
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
            "➕ Thêm Hợp đồng Tạm ứng",
            "💼 Quản lý Hợp đồng",
            "✅ Duyệt HĐ chờ",
            "📦 Export & Drive",
            "🗂 Audit log",
        ])
    else:
        page = st.radio("Menu", [
            "📊 Dashboard (Của phòng)",
            "➕ Thêm Hợp đồng Tạm ứng",
            "💼 Danh sách Hợp đồng",
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


def shorten_company_name(name):
    if not name: return ""
    s = str(name).upper()
    prefixes = [
        "CÔNG TY", "CTCP", "CỔ PHẦN", "TRÁCH NHIỆM HỮU HẠN", "TNHH", "MTV", 
        "THƯƠNG MẠI", "TM", "DỊCH VỤ", "DV", "ĐẦU TƯ", "XÂY DỰNG", 
        "PHÁT TRIỂN", "TẬP ĐOÀN", "VÀ", "&", "VẬT LIỆU", "SẢN XUẤT", 
        "KINH DOANH", "XUẤT NHẬP KHẨU", "CỔ PHẦN"
    ]
    for p in prefixes:
        s = s.replace(p, "")
    s = " ".join(s.split()) # normalize spaces
    if not s: return str(name)[:15] # fallback
    return (s[:15] + '..') if len(s) > 15 else s


def compute_hd_status(r):
    today = date.today()
    summary = db.calc_summary(r["ma_hop_dong"])
    if not summary: return summary, "?"
    nkt = r["ngay_ket_thuc_hd"]
    if isinstance(nkt, str):
        nkt = datetime.strptime(nkt, "%Y-%m-%d").date()
    han_cuoi = nkt - timedelta(days=30)
    
    if summary["tong_giai_ngan"] == 0:
        tt = "Chưa giải ngân"
    elif summary["hd_luy_ke"] >= summary["tong_giai_ngan"]: 
        tt = "Hoàn tất"
    elif today > han_cuoi: tt = "Quá hạn"
    elif (han_cuoi - today).days <= 15: tt = "Sắp đến hạn"
    else: tt = "Đang theo dõi"
    
    summary["han_cuoi"] = han_cuoi
    return summary, tt


# ============ PAGE: DASHBOARD ============
def page_dashboard():
    st.title("📊 Dashboard")
    phong = uinfo["dept"] if is_phong_kh else None
    hd_list = db.list_hop_dong(phong=phong)

    # --- Filters ---
    kh_list = sorted(list(set([r["khach_hang"] for r in hd_list if r["khach_hang"]])))
    dvth_list = sorted(list(set([r["don_vi_thu_huong"] for r in hd_list if r["don_vi_thu_huong"]])))
    
    with st.expander("🔍 Lọc dữ liệu", expanded=False):
        c1, c2 = st.columns(2)
        kh_filters = c1.multiselect("Khách hàng", kh_list)
        dvth_filters = c2.multiselect("Đơn vị thụ hưởng", dvth_list)
        
    if kh_filters:
        hd_list = [r for r in hd_list if r["khach_hang"] in kh_filters]
    if dvth_filters:
        hd_list = [r for r in hd_list if r["don_vi_thu_huong"] in dvth_filters]

    total_gn = 0
    total_hd = 0
    qua_han = sap_han = hoan_tat = 0
    rows_display = []
    
    for r in hd_list:
        s, tt = compute_hd_status(r)
        total_gn += s["tong_giai_ngan"]
        total_hd += s["hd_luy_ke"]
        if tt == "Quá hạn": qua_han += 1
        elif tt == "Sắp đến hạn": sap_han += 1
        elif tt == "Hoàn tất": hoan_tat += 1
        loai = r["loai_tu"]
        rows_display.append({
            "Ngày giải ngân": fmt_date(s.get("ngay_giai_ngan_dau")),
            "Mã giải ngân": r["ma_hop_dong"], "Khách hàng": r["khach_hang"],
            "Số hợp đồng": r["so_hd"] or "-",
            "ĐV thụ hưởng": r['don_vi_thu_huong'] or "",
            "Loại": "Từng đợt" if loai == "khau_tru_dot" else "1 lần",
            "Phòng": r["phong_phu_trach"] or "",
            "Tổng giải ngân": s["tong_giai_ngan"], "HĐ bổ sung": s["hd_luy_ke"],
            "Dư cần bổ sung": s["du_can_bo_sung"],
            "Hạn bổ sung": fmt_date(s["han_cuoi"]),
            "% Hoàn thành": s["pct_hoan_thanh"], "Trạng thái": tt,
        })

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tổng số Hợp đồng", len(hd_list))
    c2.metric("Đã giải ngân (tr)", f"{total_gn/1e6:,.0f}")
    c3.metric("Đã thu HĐ (tr)", f"{total_hd/1e6:,.0f}")
    c4.metric("Tỷ lệ thu HĐ", f"{(total_hd/total_gn*100 if total_gn else 0):.1f}%")

    c1, c2, c3 = st.columns(3)
    c1.metric("🔴 Quá hạn", qua_han)
    c2.metric("🟡 Sắp đến hạn", sap_han)
    c3.metric("🟢 Hoàn tất", hoan_tat)

    if rows_display:
        df = pd.DataFrame(rows_display)
        df["Tổng giải ngân"] = df["Tổng giải ngân"].apply(fmt_vnd)
        df["HĐ bổ sung"] = df["HĐ bổ sung"].apply(fmt_vnd)
        df["Dư cần bổ sung"] = df["Dư cần bổ sung"].apply(fmt_vnd)
        df["% Hoàn thành"] = df["% Hoàn thành"].apply(lambda x: f"{x*100:.1f}%")
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Chưa có hợp đồng nào.")


# ============ PAGE: QUAN LY HOP DONG ============
def page_hop_dong():
    st.title("💼 Quản lý Hợp đồng & Bổ sung Hóa đơn")

    st.subheader("🔍 Tìm kiếm")
    fc1, fc2, fc3 = st.columns([3, 1, 1])
    search_text = fc1.text_input("Tìm kiếm chung", placeholder="Nhập tên KH, Đơn vị thụ hưởng, mã HĐ, số HĐ...")
    filter_phong = fc2.selectbox("Phòng", ["Tất cả", "PGD Hàng Xanh", "PGD Đinh Tiên Hoàng", "PGD Đakao", "PGD Nguyễn Oanh", "PGD Tân Thới Hiệp", "KHDN1", "KHDN2", "KH FDI"])
    filter_loai = fc3.selectbox("Loại", ["Tất cả", "Khấu trừ từng đợt", "Thanh toán 1 lần"])

    phong_filter = None if is_qttd else uinfo["dept"]
    all_rows = db.list_hop_dong(phong=phong_filter)
    filtered = []
    for r in all_rows:
        loai = r["loai_tu"]
        if filter_phong != "Tất cả" and r["phong_phu_trach"] != filter_phong: continue
        if filter_loai == "Khấu trừ từng đợt" and loai != "khau_tru_dot": continue
        if filter_loai == "Thanh toán 1 lần" and loai != "mot_lan": continue
        if search_text:
            q = search_text.strip().upper()
            searchable = f"{r['ma_hop_dong']} {r['khach_hang']} {r['don_vi_thu_huong']} {r['so_hd']} {r['ghi_chu']}".upper()
            if q not in searchable: continue
            
        # Tinh toan summary de su dung trong dropdown hien thi
        s, tt = compute_hd_status(r)
        
        # Format string cho dropdown: BCONS-số HĐ-số tiền-đơn vị thụ hưởng
        kh_short = shorten_company_name(r['khach_hang'])
        dv_short = shorten_company_name(r['don_vi_thu_huong'])
        so_hd = r['so_hd'] or "Chưa rõ"
        tien = f"{fmt_vnd_dot(s['tong_giai_ngan'])}đ" if s['tong_giai_ngan'] else "0đ"
        
        display_name = f"{kh_short} - HĐ: {so_hd} - GN: {tien}"
        if dv_short: display_name += f" - ĐVTH: {dv_short}"
        
        filtered.append({
            "data": r,
            "summary": s,
            "tt": tt,
            "display": display_name
        })

    if not filtered:
        st.info("Không tìm thấy hợp đồng nào.")
        return

    selected_idx = st.selectbox(
        "📌 Chọn Hợp đồng để xem chi tiết & bổ sung hóa đơn:",
        range(len(filtered)),
        format_func=lambda i: filtered[i]["display"]
    )
    
    selected_item = filtered[selected_idx]
    selected = selected_item["data"]
    s = selected_item["summary"]
    tt = selected_item["tt"]
    loai = selected["loai_tu"]

    if loai == "khau_tru_dot":
        tab_names = ["📄 Chi tiết HĐ", "💸 Các đợt Giải ngân", "📋 HSTT", "📤 Bổ sung HĐ", "🧾 DS Hóa đơn"]
    else:
        tab_names = ["📄 Chi tiết HĐ", "💸 Các đợt Giải ngân", "📤 Bổ sung HĐ", "🧾 DS Hóa đơn"]
        
    tabs = st.tabs(tab_names)

    # --- TAB: Chi tiet HD ---
    with tabs[0]:
        st.markdown("#### Thông tin Hợp đồng")
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"**Mã HĐ:** `{selected['ma_hop_dong']}`")
        c2.markdown(f"**Khách hàng:** {selected['khach_hang']}")
        c3.markdown(f"**Trạng thái:** {status_badge(tt)}")
        c4.markdown(f"**Loại:** {'Khấu trừ từng đợt' if loai == 'khau_tru_dot' else 'Thanh toán 1 lần'}")

        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"**Số HĐ:** {selected['so_hd'] or '-'}")
        c2.markdown(f"**ĐV thụ hưởng:** {selected['don_vi_thu_huong'] or '-'}")
        c3.markdown(f"**Ngày KT HĐ:** {fmt_date(selected['ngay_ket_thuc_hd'])}")
        c4.markdown(f"**Phòng phụ trách:** {selected['phong_phu_trach'] or '-'}")
        
        if selected["ghi_chu"]:
            st.markdown(f"**Ghi chú:** {selected['ghi_chu']}")

        st.divider()
        st.markdown("#### Số liệu tài chính")
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"<div style='background-color:#f0f2f6;padding:10px;border-radius:5px;'><b>Giá trị HĐ</b><br><span style='font-size:1.4rem;color:#1F4E78'>{fmt_vnd_dot(selected['gia_tri_hd']) + ' ₫' if selected['gia_tri_hd'] else '-'}</span></div>", unsafe_allow_html=True)
        c2.markdown(f"<div style='background-color:#e8f4f8;padding:10px;border-radius:5px;'><b>Tổng Giải Ngân</b><br><span style='font-size:1.4rem;color:#0d6efd'>{fmt_vnd_dot(s['tong_giai_ngan'])} ₫</span></div>", unsafe_allow_html=True)
        c3.markdown(f"<div style='background-color:#e6f4ea;padding:10px;border-radius:5px;'><b>Đã thu HĐ</b><br><span style='font-size:1.4rem;color:#198754'>{fmt_vnd_dot(s['hd_luy_ke'])} ₫</span></div>", unsafe_allow_html=True)
        c4.markdown(f"<div style='background-color:#fce8e6;padding:10px;border-radius:5px;'><b>Còn phải thu</b><br><span style='font-size:1.4rem;color:#dc3545'>{fmt_vnd_dot(s['du_can_bo_sung'])} ₫</span></div>", unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.progress(min(s["pct_hoan_thanh"], 1.0), text=f"Hoàn thành: {s['pct_hoan_thanh']*100:.1f}%")

    # --- TAB: Giai ngan ---
    with tabs[1]:
        gns = db.list_tam_ung(selected["ma_hop_dong"])
        if gns:
            df_gn = pd.DataFrame([{
                "Mã giải ngân": g["ma_giai_ngan"],
                "Ngày giải ngân": fmt_date(g["ngay_giai_ngan"]),
                "Số tiền": fmt_vnd(g["so_tien_tu"]),
                "Ghi chú": g["ghi_chu"]
            } for g in gns])
            st.dataframe(df_gn, use_container_width=True, hide_index=True)
        else:
            st.info("Chưa có đợt giải ngân nào.")
            
        with st.expander("➕ Thêm đợt giải ngân mới cho HĐ này"):
            with st.form(f"add_gn_{selected['ma_hop_dong']}"):
                c1, c2 = st.columns(2)
                stien_txt = c1.text_input("Số tiền giải ngân (VND) *", placeholder="VD: 50.000.000")
                ngay_gn = c2.date_input("Ngày giải ngân", value=date.today(), format="DD/MM/YYYY")
                ghi_chu = st.text_input("Ghi chú")
                stien = parse_vnd_input(stien_txt)
                if stien:
                    st.caption(f"= {fmt_vnd_dot(stien)} VND")
                    
                if st.form_submit_button("Lưu đợt giải ngân", type="primary"):
                    if not stien:
                        st.error("Vui lòng nhập số tiền hợp lệ!")
                    else:
                        ma_gn = db.generate_ma_giai_ngan(selected["khach_hang"], year=ngay_gn.year)
                        db.add_tam_ung({
                            "ma_giai_ngan": ma_gn, "ma_hop_dong": selected["ma_hop_dong"],
                            "so_tien_tu": stien, "ngay_giai_ngan": ngay_gn, "ghi_chu": ghi_chu
                        }, user)
                        st.success(f"Đã thêm đợt giải ngân {ma_gn}")
                        st.rerun()

    tab_offset = 1
    # --- TAB: HSTT ---
    if loai == "khau_tru_dot":
        with tabs[2]:
            hstt_rows = db.list_hstt(selected["ma_hop_dong"])
            if hstt_rows:
                data = []
                for r in hstt_rows:
                    kt = r["kl_truoc_vat"] * selected["pct_khau_tru"]
                    data.append({
                        "Đợt": r["dot_so"],
                        "Ngày HSTT": fmt_date(r["ngay_hstt"]),
                        "KL trước VAT": fmt_vnd(r["kl_truoc_vat"]),
                        "Khấu trừ": fmt_vnd(kt),
                        "Ghi chú": r["ghi_chu"] or "",
                    })
                st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
            else:
                st.info("Chưa có HSTT nào.")

            with st.expander("➕ Thêm đợt HSTT mới"):
                with st.form(f"hstt_{selected['ma_hop_dong']}"):
                    next_dot = max([r["dot_so"] for r in hstt_rows], default=0) + 1
                    c1, c2 = st.columns(2)
                    dot = c1.number_input("Đợt #", min_value=1, value=next_dot)
                    ngay = c2.date_input("Ngày HSTT", value=date.today(), format="DD/MM/YYYY")
                    kl_text = st.text_input("KL trước VAT (VND)", placeholder="VD: 1.000.000.000")
                    ghi_chu = st.text_input("Ghi chú")
                    kl = parse_vnd_input(kl_text)
                    if kl:
                        st.caption(f"= {fmt_vnd_dot(kl)} VND → Khấu trừ: {fmt_vnd_dot(kl * selected['pct_khau_tru'])} VND")
                    if st.form_submit_button("Thêm HSTT", type="primary"):
                        if not kl or kl <= 0:
                            st.error("Nhập KL hợp lệ!")
                        else:
                            db.add_hstt({"ma_hop_dong": selected["ma_hop_dong"], "dot_so": int(dot),
                                         "ngay_hstt": ngay, "kl_truoc_vat": kl, "ghi_chu": ghi_chu}, user)
                            st.rerun()
        tab_offset = 2

    # --- TAB: Bo sung HD ---
    with tabs[1 + tab_offset]:
        st.subheader("Upload hóa đơn bổ sung")
        files = st.file_uploader("Chọn file XML/PDF", accept_multiple_files=True, type=["xml", "pdf"], key=f"up_{selected['ma_hop_dong']}")
        
        if loai == "khau_tru_dot":
            hstt_list = db.list_hstt(selected["ma_hop_dong"])
            max_dot = max([r["dot_so"] for r in hstt_list], default=1)
            dot_sel = st.number_input("Gán vào đợt #", min_value=1, value=max_dot, step=1, key=f"dot_{selected['ma_hop_dong']}")
        else:
            dot_sel = 1

        if files and st.button("📥 Trích xuất file"):
            ok = 0
            for f in files:
                d = parsers.parse_file(f)
                d["ma_hop_dong"] = selected["ma_hop_dong"]
                d["dot_so"] = int(dot_sel)
                db.add_staging(d, user)
                ok += 1
            st.success(f"Đã trích xuất {ok} file. Vui lòng Xác nhận bên dưới!")
            st.rerun()

        stagings = [s for s in db.list_staging(user=user if is_phong_kh else None) if s["ma_hop_dong"] == selected["ma_hop_dong"]]
        if stagings:
            st.markdown("##### 📝 Hóa đơn chờ xác nhận")
            for s in stagings:
                with st.expander(f"HĐ: {s['so_hd'] or 'Chưa rõ'} - {s['file_src'] or ''}", expanded=True):
                    with st.form(f"cf_{s['id']}"):
                        c1, c2 = st.columns(2)
                        so_hd = c1.text_input("Số hóa đơn *", value=s['so_hd'] or "")
                        def_date = date.today()
                        if s['ngay_hd']:
                            try:
                                def_date = datetime.strptime(s["ngay_hd"], "%Y-%m-%d").date() if isinstance(s["ngay_hd"], str) else s["ngay_hd"]
                            except: pass
                        ngay_hd = c2.date_input("Ngày hóa đơn", value=def_date, format="DD/MM/YYYY")
                        
                        c1, c2 = st.columns(2)
                        ten_ban = c1.text_input("Tên người bán", value=s['ten_ban'] or "")
                        mst = c2.text_input("MST người bán", value=s['mst_ban'] or "")
                        
                        tien_text = c1.text_input("Tiền trước VAT *", value=f"{int(s['tien_truoc_vat'])}" if s['tien_truoc_vat'] else "")
                        vat_text = c2.text_input("Tiền VAT", value=f"{int(s['vat'])}" if s['vat'] else "")
                        
                        tien = parse_vnd_input(tien_text)
                        vat = parse_vnd_input(vat_text) or 0
                        
                        dvth = selected['don_vi_thu_huong'] or ""
                        norm_dvth = db.normalize_company_name(dvth) if dvth else ""
                        norm_tb = db.normalize_company_name(ten_ban) if ten_ban else ""
                        
                        mismatch = False
                        if norm_dvth and norm_tb and norm_dvth != norm_tb:
                            st.warning(f"⚠️ Cảnh báo: Tên người bán ({ten_ban}) KHÔNG KHỚP với Đơn vị thụ hưởng ({dvth})!")
                            mismatch = True
                            confirm_mismatch = st.checkbox("Xác nhận Hóa đơn hợp lệ dù tên không khớp", key=f"chk_{s['id']}")
                        else:
                            confirm_mismatch = True
                        
                        c1, c2, c3 = st.columns([2, 1, 1])
                        if c2.form_submit_button("✓ Xác nhận lưu", type="primary"):
                            if mismatch and not confirm_mismatch:
                                st.error("Vui lòng tick chọn Xác nhận hợp lệ ở bên trên!")
                            elif not so_hd or not tien:
                                st.error("Nhập số HĐ và tiền!")
                            else:
                                db.add_hoa_don({
                                    "ma_hop_dong": selected["ma_hop_dong"], "dot_so": s["dot_so"],
                                    "so_hd": so_hd, "ngay_hd": ngay_hd, "mst_ban": mst, "ten_ban": ten_ban,
                                    "tien_truoc_vat": tien, "vat": vat, "tong_cong": tien + vat,
                                    "ma_tra_cuu": s['ma_tra_cuu'], "file_src": s['file_src'], "ghi_chu": f"Upload boi {user}"
                                }, user, status="approved" if is_qttd else "pending")
                                db.delete_staging(s["id"])
                                st.rerun()
                        if c3.form_submit_button("🗑️ Xóa file"):
                            db.delete_staging(s["id"])
                            st.rerun()

        with st.expander("✍️ Nhập thủ công hóa đơn"):
            with st.form(f"mn_{selected['ma_hop_dong']}"):
                c1, c2 = st.columns(2)
                m_hd = c1.text_input("Số hóa đơn *")
                m_dt = c2.date_input("Ngày hóa đơn", value=date.today(), format="DD/MM/YYYY")
                m_tien = c1.text_input("Tiền trước VAT *")
                m_vat = c2.text_input("Tiền VAT")
                
                if st.form_submit_button("Lưu hóa đơn", type="primary"):
                    tien = parse_vnd_input(m_tien)
                    vat = parse_vnd_input(m_vat) or 0
                    if not m_hd or not tien:
                        st.error("Lỗi dữ liệu")
                    else:
                        db.add_hoa_don({
                            "ma_hop_dong": selected["ma_hop_dong"], "dot_so": int(dot_sel),
                            "so_hd": m_hd, "ngay_hd": m_dt, "tien_truoc_vat": tien, "vat": vat,
                            "tong_cong": tien + vat, "file_src": "manual"
                        }, user, status="approved" if is_qttd else "pending")
                        st.rerun()

    # --- TAB: DS Hoa don ---
    with tabs[2 + tab_offset]:
        hd_list = db.list_hoa_don(ma_hop_dong=selected["ma_hop_dong"])
        if hd_list:
            for h in hd_list:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 1])
                    c1.markdown(f"**Số HĐ:** {h['so_hd']} | **Ngày:** {fmt_date(h['ngay_hd'])}")
                    c2.markdown(f"**Đợt:** {h['dot_so']} | **TT:** {status_badge(h['status'])}")
                    c2.caption(f"Tiền: {fmt_vnd(h['tien_truoc_vat'])} | VAT: {fmt_vnd(h['vat'])}")
                    if c3.button("🗑️ Xóa", key=f"del_{h['id']}"):
                        db.delete_hoa_don(h['id'], user)
                        st.rerun()
        else:
            st.info("Chưa có hóa đơn nào.")


# ============ PAGE: THEM HOP DONG MOI ============
def page_them_hop_dong():
    st.title("➕ Thêm Hợp đồng Tạm ứng mới")
    loai_tu = st.radio("Loại thanh toán *", ["Khấu trừ từng đợt", "Thanh toán 1 lần"], horizontal=True)
    is_mot_lan = loai_tu == "Thanh toán 1 lần"
    companies = db.list_distinct_companies()

    with st.form("them_hd_form"):
        c1, c2 = st.columns(2)
        kh_select = c1.selectbox("Chọn KH đã có", ["--- Nhập mới ---"] + companies) if companies else "--- Nhập mới ---"
        kh_new = c2.text_input("Hoặc nhập tên mới")
        
        c1, c2 = st.columns(2)
        dv_select = c1.selectbox("Đơn vị thụ hưởng", ["--- Nhập mới ---"] + companies) if companies else "--- Nhập mới ---"
        dv_new = c2.text_input("Hoặc nhập ĐVTH mới")
        
        c1, c2 = st.columns(2)
        so_hd = c1.text_input("Số hợp đồng *")
        phong = uinfo["dept"] if is_phong_kh else c2.selectbox("Phòng phụ trách", ["PGD Hàng Xanh", "PGD Đinh Tiên Hoàng", "PGD Đakao", "PGD Nguyễn Oanh", "PGD Tân Thới Hiệp", "KHDN1", "KHDN2", "KH FDI"])
        
        c1, c2 = st.columns(2)
        gtri_text = c1.text_input("Giá trị HĐ (VND)")
        tu_text = c2.text_input("Số tiền tạm ứng Đợt 1 *")
        
        c1, c2 = st.columns(2)
        ngay_gn = c1.date_input("Ngày giải ngân đợt 1", value=date.today(), format="DD/MM/YYYY")
        ngay_kt = c2.date_input("Ngày kết thúc HĐ", value=date.today() + timedelta(days=180), format="DD/MM/YYYY")
        
        pct = 0.0 if is_mot_lan else c1.number_input("% Khấu trừ/đợt", value=0.1, step=0.01)
        ghi_chu = st.text_area("Ghi chú")
        
        gtri = parse_vnd_input(gtri_text)
        tu_amt = parse_vnd_input(tu_text)

        if st.form_submit_button("➕ Lưu Hợp đồng & Giải ngân đợt 1", type="primary"):
            kh = kh_new.strip() or (kh_select if kh_select != "--- Nhập mới ---" else "")
            dvth = dv_new.strip() or (dv_select if dv_select != "--- Nhập mới ---" else "")
            
            if not kh or not tu_amt:
                st.error("Nhập đầy đủ Khách hàng và Số tiền!")
            else:
                ma_hd = db.generate_ma_hop_dong(kh, year=ngay_gn.year)
                # Kiem tra neu hop dong da ton tai -> co the gop (nhung tam thoi tao moi theo form nay)
                
                db.add_hop_dong({
                    "ma_hop_dong": ma_hd, "khach_hang": kh, "don_vi_thu_huong": dvth,
                    "so_hd": so_hd, "gia_tri_hd": gtri, "ngay_ket_thuc_hd": ngay_kt,
                    "loai_tu": "mot_lan" if is_mot_lan else "khau_tru_dot",
                    "pct_khau_tru": pct, "phong_phu_trach": phong, "ghi_chu": ghi_chu
                }, user)
                
                ma_gn = db.generate_ma_giai_ngan(kh, year=ngay_gn.year)
                db.add_tam_ung({
                    "ma_giai_ngan": ma_gn, "ma_hop_dong": ma_hd,
                    "so_tien_tu": tu_amt, "ngay_giai_ngan": ngay_gn, "ghi_chu": "Giải ngân lần 1"
                }, user)
                
                st.success(f"✅ Tạo thành công Hợp đồng: {ma_hd} và Đợt giải ngân: {ma_gn}")


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
            if c2.button("✓ Duyệt", key=f"app_{h['id']}", type="primary"):
                db.approve_hoa_don(h["id"], user)
                st.rerun()
            if c2.button("✗ Từ chối", key=f"rej_{h['id']}"):
                db.reject_hoa_don(h["id"], user, "Từ chối")
                st.rerun()

# ============ ROUTE ============
if page.startswith("📊 Dashboard"):
    page_dashboard()
elif page == "➕ Thêm Hợp đồng Tạm ứng":
    page_them_hop_dong()
elif page in ("💼 Quản lý Hợp đồng", "💼 Danh sách Hợp đồng"):
    page_hop_dong()
elif page == "✅ Duyệt HĐ chờ":
    page_duyet_hd()
elif page == "📦 Export & Drive":
    st.title("📦 Xuất báo cáo Excel")
    st.write("Xuất toàn bộ dữ liệu Hợp đồng, Giải ngân, Hóa đơn ra file Excel theo chuẩn.")
    if st.button("📥 Xuất file Excel", type="primary"):
        with st.spinner("Đang xử lý dữ liệu..."):
            try:
                path = exporter.export_excel()
                with open(path, "rb") as f:
                    st.download_button(
                        label="Tải file Excel về máy",
                        data=f,
                        file_name=os.path.basename(path),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                st.success("Tạo file thành công!")
            except Exception as e:
                st.error(f"Lỗi khi xuất file: {e}")
elif page == "🗂 Audit log":
    st.dataframe(pd.DataFrame([dict(r) for r in db.recent_audit(100)]), use_container_width=True)
