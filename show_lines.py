import sys
sys.stdout.reconfigure(encoding='utf-8')
with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if 'st.radio("Menu"' in line or 'st.subheader("Upload' in line or 'st.file_uploader' in line or 'st.subheader("Nh' in line or 'page.startswith' in line or 'page in' in line or 'page == ' in line or 'st.selectbox("Ch' in line:
        print(f'{i}: {repr(line)}')
