import sys

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update the menu items
if 'if is_qttd:' in content:
    content = content.replace(
        'page = st.radio("Menu", [\n            "📊 Dashboard",\n            "💼 Quản lý Tạm ứng",\n            "⏳ Duyệt HĐ chờ",\n            "📥 Export & Drive",\n            "📜 Audit log",\n        ])',
        'page = st.radio("Menu", [\n            "📊 Dashboard",\n            "➕ Thêm món tạm ứng mới",\n            "💼 Quản lý Tạm ứng",\n            "⏳ Duyệt HĐ chờ",\n            "📥 Export & Drive",\n            "📜 Audit log",\n        ])'
    )
    content = content.replace(
        'page = st.radio("Menu", [\n            "📊 Dashboard (Của phòng)",\n            "💼 Danh sách Tạm ứng",\n        ])',
        'page = st.radio("Menu", [\n            "📊 Dashboard (Của phòng)",\n            "➕ Thêm món tạm ứng mới",\n            "💼 Danh sách Tạm ứng",\n        ])'
    )

# 2. Extract "Thêm món tạm ứng mới" logic from page_tam_ung
# We will split the file
them_mon_start = content.find('# ------ THEM MON MOI ------')
if them_mon_start != -1:
    them_mon_end = content.find('# ============ PAGE: DUYET HD ============', them_mon_start)
    
    # Extract the block
    them_mon_block = content[them_mon_start:them_mon_end]
    
    # Define new page function
    new_page_func = "\n# ============ PAGE: THEM MON TAM UNG MOI ============\ndef page_them_tam_ung():\n    st.title(\"➕ Thêm món tạm ứng mới\")\n"
    
    # The block inside page_tam_ung currently has an expander. We should un-indent it and remove expander.
    # Wait, simple way: keep the expander or just remove `with st.expander(...)` and unindent.
    # Actually, let's keep it simple: just take `them_mon_block` and replace `st.divider()\n    with st.expander("➕ Thêm món Tạm ứng mới"):` with just the content.
    
    block_lines = them_mon_block.split('\n')
    new_lines = []
    in_expander = False
    for line in block_lines:
        if line.strip() == '# ------ THEM MON MOI ------':
            continue
        if line.strip() == 'st.divider()':
            continue
        if 'with st.expander(' in line:
            in_expander = True
            continue
        
        if in_expander:
            if line.startswith('        '):
                new_lines.append('    ' + line[8:])
            elif line.startswith('    '):
                new_lines.append(line)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
            
    page_func_code = new_page_func + '\n'.join(new_lines) + '\n'
    
    # Remove from old place, insert the new function
    content = content[:them_mon_start] + page_func_code + content[them_mon_end:]

# 3. Add to routing
if 'elif page.startswith("💼"): page_tam_ung()' in content:
    content = content.replace(
        'elif page.startswith("💼"): page_tam_ung()',
        'elif page.startswith("➕"): page_them_tam_ung()\n    elif page.startswith("💼"): page_tam_ung()'
    )

# 4. Fix specific labels as requested
replacements = {
    'Chon mon tam ung de thao tac:': 'Chọn món tạm ứng để thao tác:',
    'Chon món tam ung de thao tac:': 'Chọn món tạm ứng để thao tác:',
    'Upload hoa don bo sung': 'Upload hóa đơn bổ sung',
    'Chon file XML/PDF hoa don': 'Chọn file XML/PDF hóa đơn',
    'Nhap thu cong hoa dơn': 'Nhập thủ công hóa đơn',
    'Nhap thu cong hoa don': 'Nhập thủ công hóa đơn'
}

for k, v in replacements.items():
    content = content.replace(k, v)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Refactoring complete.")
