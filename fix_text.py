import sys

def replace_all(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    replacements = {
        'Theo doi Tam ung & HD': 'Theo dõi Tạm ứng & HĐ',
        'He thong theo doi Tam ung & Bo sung Hoa don': 'Hệ thống theo dõi Tạm ứng & Bổ sung Hóa đơn',
        'Dang nhap de tiep tuc': 'Đăng nhập để tiếp tục',
        'Chon user': 'Chọn user',
        'Dang nhap': 'Đăng nhập',
        'Dang xuat': 'Đăng xuất',
        'Phong:': 'Phòng:',
        'Quan ly Tam ung': 'Quản lý Tạm ứng',
        'Duyet HD cho': 'Duyệt HĐ chờ',
        'Dashboard (cua phong)': 'Dashboard (Của phòng)',
        'Danh sach Tam ung': 'Danh sách Tạm ứng',
        'Hoan tat': 'Hoàn tất',
        'Qua han': 'Quá hạn',
        'Sap den han': 'Sắp đến hạn',
        'Dang theo doi': 'Đang theo dõi',
        'Tong mon TU': 'Tổng món TU',
        'Gia tri TU (tr)': 'Giá trị TU (tr)',
        'Da bo sung HD (tr)': 'Đã bổ sung HĐ (tr)',
        'Ty le bo sung': 'Tỷ lệ bổ sung',
        'Loai thanh toan *': 'Loại thanh toán *',
        'Khau tru tung dot': 'Khấu trừ từng đợt',
        'Thanh toan 1 lan': 'Thanh toán 1 lần',
        'Chon KH da co': 'Chọn KH đã có',
        '--- Nhap cong ty moi ---': '--- Nhập công ty mới ---',
        'Hoac nhap ten moi': 'Hoặc nhập tên mới',
        'He thong tu chuan hoa ten': 'Hệ thống tự chuẩn hóa tên',
        'So hop dong': 'Số hợp đồng',
        'Phong phu trach': 'Phòng phụ trách',
        'Gia tri HD (VND)': 'Giá trị HĐ (VND)',
        'So tien tam ung *': 'Số tiền tạm ứng *',
        'Ngay giai ngan': 'Ngày giải ngân',
        'Ngay ket thuc HD': 'Ngày kết thúc HĐ',
        'Ghi chu': 'Ghi chú',
        'Tam ung:': 'Tạm ứng:',
        'Nhap ten khach hang!': 'Nhập tên khách hàng!',
        'Nhap so tien tam ung!': 'Nhập số tiền tạm ứng!',
        '"1 lan"': '"1 lần"',
        'Khong tim thay mon tam ung nao phu hop.': 'Không tìm thấy món tạm ứng nào phù hợp.',
        'Hien thi ': 'Hiển thị ',
        ' mon': ' món',
        'Tung dot': 'Từng đợt',
        'Khach hang': 'Khách hàng',
        'Da bo sung': 'Đã bổ sung',
        'Con lai': 'Còn lại',
        'Trang thai': 'Trạng thái',
        'Chon mon tam ung de thao tac:': 'Chọn món tạm ứng để thao tác:',
        'Thong tin chung': 'Thông tin chung',
        'Ma ho so:': 'Mã hồ sơ:',
        'Them mon Tam ung moi': 'Thêm món Tạm ứng mới',
        'Loi:': 'Lỗi:',
        'Khong co HD cho duyet.': 'Không có HĐ chờ duyệt.',
        'Them': 'Thêm',
        'Khac': 'Khác'
    }

    for k, v in replacements.items():
        content = content.replace(k, v)

    # Specific replacements
    content = content.replace('["KHDN", "SME", "FDI", "Khac"]', '["PGD Hàng Xanh", "PGD Đinh Tiên Hoàng", "PGD Đakao", "PGD Nguyễn Oanh", "PGD Tân Thới Hiệp", "KHDN1", "KHDN2", "KH FDI"]')
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

replace_all('d:/CLAUDE CODE/hoa don tam ung/outputs/app/app.py')
print('Fixed Vietnamese texts in app.py')
