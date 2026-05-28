with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

replacements = {
    'st.radio("Menu", [\n            "📊 Dashboard",\n            "💰 Quản lý Tạm ứng",\n            "✅ Duyệt HĐ chờ",\n            "📦 Export & Drive",\n            "🗂 Audit log",\n        ])': 'st.radio("Menu", [\n            "📊 Dashboard",\n            "➕ Thêm món tạm ứng mới",\n            "💰 Quản lý Tạm ứng",\n            "✅ Duyệt HĐ chờ",\n            "📦 Export & Drive",\n            "🗂 Audit log",\n        ])',
    'st.radio("Menu", [\n            "📊 Dashboard (Của phòng)",\n            "💰 Danh sách Tạm ứng",\n        ])': 'st.radio("Menu", [\n            "📊 Dashboard (Của phòng)",\n            "➕ Thêm món tạm ứng mới",\n            "💰 Danh sách Tạm ứng",\n        ])',
    'elif page in ("💰 Quản lý Tạm ứng", "💰 Danh sách Tạm ứng"):\n    page_tam_ung()': 'elif page == "➕ Thêm món tạm ứng mới":\n    page_them_tam_ung()\nelif page in ("💰 Quản lý Tạm ứng", "💰 Danh sách Tạm ứng"):\n    page_tam_ung()',
    '"📌 Chon mon tam ung de thao tac:"': '"📌 Chọn món tạm ứng để thao tác:"',
    '"Upload hoa don bo sung"': '"Upload hóa đơn bổ sung"',
    '"Chon file XML/PDF hoa don"': '"Chọn file XML/PDF hóa đơn"',
    '"Nhap thu cong hoa don"': '"Nhập thủ công hóa đơn"',
    '"Nhap thu cong hoa dơn"': '"Nhập thủ công hóa đơn"'
}

for k, v in replacements.items():
    content = content.replace(k, v)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
