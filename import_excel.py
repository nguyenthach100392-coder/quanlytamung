import pandas as pd
from datetime import timedelta
import db
from datetime import datetime

print("Clearing old data...")
with db.get_conn() as c:
    c.execute("DELETE FROM staging_hd")
    c.execute("DELETE FROM hoa_don")
    c.execute("DELETE FROM hstt")
    c.execute("DELETE FROM audit_log")
    c.execute("DELETE FROM tam_ung")
    
print("Loading Excel file...")
df = pd.read_excel('D:/bcons_tam_ung_filled.xlsx')

success = 0
for idx, row in df.iterrows():
    if pd.isna(row.get('TÊN KHÁCH HÀNG')):
        continue
        
    kh = str(row['TÊN KHÁCH HÀNG']).strip()
    dvth = str(row['ĐƠN VỊ THỤ HƯỞNG']).strip() if not pd.isna(row.get('ĐƠN VỊ THỤ HƯỞNG')) else ""
    so_hd = str(row['SỐ HỢP ĐỒNG']).strip() if not pd.isna(row.get('SỐ HỢP ĐỒNG')) else ""
    
    tu_amt = float(row['SỐ TIỀN TẠM ỨNG']) if not pd.isna(row.get('SỐ TIỀN TẠM ỨNG')) else 0
    
    ngay_gn_raw = row['NGÀY GIẢI NGÂN']
    if pd.isna(ngay_gn_raw):
        ngay_gn = datetime.today().date()
    else:
        if isinstance(ngay_gn_raw, datetime):
            ngay_gn = ngay_gn_raw.date()
        else:
            try:
                ngay_gn = pd.to_datetime(ngay_gn_raw).date()
            except:
                ngay_gn = datetime.today().date()
                
    loai_raw = str(row.get('LOẠI TÁM ỨNG', '')).strip().lower()
    if 'khấu trừ' in loai_raw or 'khau tru' in loai_raw:
        loai_tu = 'khau_tru_dot'
        pct = 0.3
    else:
        loai_tu = 'mot_lan'
        pct = 0.0
        
    phong = str(row['PHÒNG PHỤ TRÁCH']).strip() if not pd.isna(row.get('PHÒNG PHỤ TRÁCH')) else ""
    
    ngay_kt = ngay_gn + timedelta(days=180)
    
    ma = db.generate_ma_giai_ngan(kh)
    
    tu_data = {
        "ma_giai_ngan": ma,
        "khach_hang": kh,
        "don_vi_thu_huong": dvth,
        "so_hd": so_hd,
        "gia_tri_hd": None,
        "so_tien_tu": tu_amt,
        "ngay_giai_ngan": ngay_gn,
        "ngay_ket_thuc_hd": ngay_kt, # Must be NOT NULL per schema
        "loai_tu": loai_tu,
        "pct_khau_tru": pct,
        "phong_phu_trach": phong,
        "ghi_chu": None
    }
    
    try:
        db.add_tam_ung(tu_data, "admin")
        success += 1
    except Exception as e:
        print(f"Error inserting row {idx}: {e}")

print(f"Done! Imported {success} records.")
