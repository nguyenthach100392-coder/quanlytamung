"""Script tao du lieu mau de test."""
import db
from datetime import date, timedelta

db.init_db()

samples = [
    {"kh": "Cong ty TNHH ABC Viet Nam", "so_hd": "HD-2026-0158", "gtri": 5_000_000_000, "tu": 500_000_000,
     "phong": "KHDN", "loai": "khau_tru_dot", "pct": 0.1, "ghi_chu": "Du an xay dung nha xuong KCN"},
    {"kh": "CTCP Thuong mai XYZ", "so_hd": "HD-2026-0205", "gtri": 2_000_000_000, "tu": 200_000_000,
     "phong": "SME", "loai": "mot_lan", "pct": 0, "ghi_chu": "Cung cap vat tu - thanh toan 1 lan"},
    {"kh": "Cong ty TNHH ABC Viet Nam", "so_hd": "HD-2026-0300", "gtri": 3_000_000_000, "tu": 300_000_000,
     "phong": "KHDN", "loai": "khau_tru_dot", "pct": 0.1, "ghi_chu": "Du an nha kho lan 2"},
    {"kh": "Cong ty CP Dai Phat", "so_hd": "HD-2026-0410", "gtri": 8_000_000_000, "tu": 800_000_000,
     "phong": "KHDN", "loai": "khau_tru_dot", "pct": 0.15, "ghi_chu": "Hop dong thi cong duong"},
    {"kh": "DNTN Thanh Hung", "so_hd": "HD-2026-0501", "gtri": 1_500_000_000, "tu": 150_000_000,
     "phong": "SME", "loai": "mot_lan", "pct": 0, "ghi_chu": "Mua thiet bi van phong"},
]

for i, s in enumerate(samples):
    ngay_gn = date.today() - timedelta(days=30*(i+1))
    ngay_kt = ngay_gn + timedelta(days=180)
    ma = db.generate_ma_giai_ngan(s["kh"])
    db.add_tam_ung({
        "ma_giai_ngan": ma, "khach_hang": s["kh"], "so_hd": s["so_hd"],
        "gia_tri_hd": s["gtri"], "so_tien_tu": s["tu"],
        "ngay_giai_ngan": ngay_gn, "ngay_ket_thuc_hd": ngay_kt,
        "loai_tu": s["loai"], "pct_khau_tru": s["pct"],
        "phong_phu_trach": s["phong"], "ghi_chu": s["ghi_chu"],
    }, "admin")
    print(f"  {ma} | {s['kh'][:30]} | {s['loai']}")

# Add some HSTT for khau_tru_dot entries
tu_list = db.list_tam_ung()
for r in tu_list:
    if r["loai_tu"] == "khau_tru_dot":
        db.add_hstt({"ma_giai_ngan": r["ma_giai_ngan"], "dot_so": 1,
                     "ngay_hstt": date.today() - timedelta(days=15),
                     "kl_truoc_vat": r["gia_tri_hd"] * 0.3, "ghi_chu": "Dot 1"}, "admin")
        print(f"  HSTT dot 1 cho {r['ma_giai_ngan']}")

print("\nDone! Tao xong du lieu mau.")
