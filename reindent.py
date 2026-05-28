with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if i >= 563: # inside page_duyet_hd and page_export
        # We need to re-indent:
        stripped = line.strip()
        if stripped == 'st.success("Không có HĐ chờ duyệt.")': new_lines.append('        ' + stripped + '\n')
        elif stripped == 'return': new_lines.append('        ' + stripped + '\n')
        elif stripped == 'with st.container(border=True):': new_lines.append('        ' + stripped + '\n')
        elif stripped == 'st.subheader("Tải file Excel về máy")': new_lines.append('        ' + stripped + '\n')
        elif stripped.startswith('if st.button("Xuất file Excel"'): new_lines.append('        ' + stripped + '\n')
        elif stripped == 'out = exporter.export_excel()': new_lines.append('            ' + stripped + '\n')
        elif stripped == 'with open(out, "rb") as f:': new_lines.append('            ' + stripped + '\n')
        elif stripped == 'data = f.read()': new_lines.append('                ' + stripped + '\n')
        elif stripped.startswith('st.download_button'): new_lines.append('            ' + stripped + '\n')
        elif stripped.startswith('file_name='): new_lines.append('            ' + stripped + '\n')
        elif stripped.startswith('mime='): new_lines.append('            ' + stripped + '\n')
        elif stripped.startswith('st.success(f"Đã xuất'): new_lines.append('            ' + stripped + '\n')
        elif stripped == 'st.subheader("Đẩy file lên folder Google Drive (sync local)")': new_lines.append('        ' + stripped + '\n')
        elif stripped.startswith('st.caption("Yêu cầu:'): new_lines.append('        ' + stripped + '\n')
        elif stripped.startswith('drive_path = '): new_lines.append('        ' + stripped + '\n')
        elif stripped.startswith('value=os.'): new_lines.append('        ' + stripped + '\n')
        elif stripped.startswith('if st.button(') and 'Push' in stripped: new_lines.append('        ' + stripped + '\n')
        elif stripped == 'try:': new_lines.append('            ' + stripped + '\n')
        elif stripped.startswith('dest, '): new_lines.append('                ' + stripped + '\n')
        elif stripped.startswith('st.success(f"Đã push'): new_lines.append('                ' + stripped + '\n')
        elif stripped == '- {dest}\\n- {latest}")': new_lines.append('                ' + stripped + '\n')
        elif stripped == 'except Exception as e:': new_lines.append('            ' + stripped + '\n')
        elif stripped.startswith('st.error(f"Lỗi:'): new_lines.append('                ' + stripped + '\n')
        else:
            new_lines.append(line)
    else:
        new_lines.append(line)

content = ''.join(new_lines)

# Fix route
content = content.replace(
    'elif page in ("💼 Quản lý Tạm ứng", "💼 Danh sách Tạm ứng"):\n    page_tam_ung()',
    'elif page == "➕ Thêm món tạm ứng mới":\n    page_them_tam_ung()\nelif page in ("💼 Quản lý Tạm ứng", "💼 Danh sách Tạm ứng"):\n    page_tam_ung()'
)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
