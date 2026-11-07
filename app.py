import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import sqlite3
import re
from datetime import datetime

# إعدادات الصفحة واللغة العربية RTL
st.set_page_config(page_title="نظام إدارة ومراقبة قسم الغذائي", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    html, body, [class*="css"]  {
        font-family: 'Cairo', sans-serif;
        direction: rtl;
        text-align: right;
    }
    </style>
""", unsafe_allow_html=True)

# إعداد قاعدة البيانات الدائمة
conn = sqlite3.connect('food_department_db.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS master_items (
    code TEXT PRIMARY KEY,
    name TEXT,
    branch_qty REAL,
    category TEXT,
    price REAL,
    cost REAL,
    brand TEXT,
    status TEXT,
    supplier TEXT,
    created_at TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS warehouse_stock (
    code TEXT PRIMARY KEY,
    wh_qty REAL,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')
conn.commit()

def extract_code(val):
    if pd.isna(val): return None
    match = re.search(r'\[(\d+)⟩', str(val)) or re.search(r'\[(\d+)\]', str(val))
    return match.group(1) if match else str(val).strip()

st.sidebar.title("📦 إدارة قسم الغذائي")
menu = st.sidebar.radio("الانتقال إلى:", [
    "لوحة التحكم الرئيسية", 
    "مراقبة وتغطية المخزون", 
    "التوصيات الذكية",
    "مركز رفع وتحديث البيانات"
])

if menu == "مركز رفع وتحديث البيانات":
    st.header("📥 رفع وتحديث الملفات اليومية")
    st.info("قم برفع الملفات لتحديث النظام فورياً دون فقدان السجلات.")
    
    f_items = st.file_uploader("ملف أصناف الغذائي", type=['xlsx'])
    f_wh = st.file_uploader("ملف رصيد المستودع", type=['xlsx'])
    
    if st.button("حفظ وتحديث قاعدة البيانات"):
        if f_items:
            df_items = pd.read_excel(f_items)
            df_items.columns = df_items.columns.str.strip()
            df_items['code'] = df_items['مرجع داخلي'].astype(str).str.strip()
            for _, row in df_items.iterrows():
                cursor.execute('''
                INSERT INTO master_items (code, name, branch_qty, category, price, cost, brand, status, supplier, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(code) DO UPDATE SET
                    name=excluded.name, branch_qty=excluded.branch_qty, category=excluded.category,
                    price=excluded.price, cost=excluded.cost, brand=excluded.brand, status=excluded.status
                ''', (row['code'], row['المنتج'], row['الكمية في اليد'], row['فئة المنتج'], 
                      row['سعر البيع'], row['التكلفة'], row['البراند'], row['حالة المنتج'], 
                      row['موقع التوريد'], str(row['أنشئ في'])))
            conn.commit()
            st.success("تم تحديث أصناف الفروع بنجاح!")

        if f_wh:
            df_wh = pd.read_excel(f_wh)
            df_wh.columns = df_wh.columns.str.strip()
            # استخراج الكود باستخدام دالة مرنة
            df_wh['code'] = df_wh['المنتج'].apply(lambda x: re.search(r'\[(\d+)\]', str(x)).group(1) if re.search(r'\[(\d+)\]', str(x)) else str(x).strip())
            for _, row in df_wh.iterrows():
                if row['code']:
                    cursor.execute('''
                    INSERT INTO warehouse_stock (code, wh_qty) VALUES (?, ?)
                    ON CONFLICT(code) DO UPDATE SET wh_qty=excluded.wh_qty
                    ''', (row['code'], row['الكمية في اليد']))
            conn.commit()
            st.success("تم تحديث رصيد المستودع بنجاح!")

else:
    df_master = pd.read_sql("SELECT * FROM master_items", conn)
    df_wh = pd.read_sql("SELECT * FROM warehouse_stock", conn)
    
    if df_master.empty:
        st.warning("⚠️ يرجى التوجه إلى 'مركز رفع وتحديث البيانات' ورفع الملفات لتبدأ اللوحة بالعمل.")
    else:
        df_full = pd.merge(df_master, df_wh, on='code', how='left')
        df_full['wh_qty'] = df_full['wh_qty'].fillna(0)
        df_full['total_stock'] = df_full['branch_qty'] + df_full['wh_qty']
        df_full['stock_cost_val'] = df_full['total_stock'] * df_full['cost']
        df_full['stock_sale_val'] = df_full['total_stock'] * df_full['price']

        if menu == "لوحة التحكم الرئيسية":
            st.title("📊 لوحة التحكم الرئيسية - قسم الغذائي")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("إجمالي الأصناف", f"{len(df_full):,} صنف")
            c2.metric("قيمة المخزون (بالتكلفة)", f"{df_full['stock_cost_val'].sum():,.2f} ر.س")
            c3.metric("قيمة المخزون (بسعر البيع)", f"{df_full['stock_sale_val'].sum():,.2f} ر.س")
            c4.metric("إجمالي رصيد المستودع", f"{df_full['wh_qty'].sum():,.0f} قطعة")
            
            st.divider()
            fig = px.pie(df_full, names='category', values='stock_cost_val', title='توزيع قيمة المخزون حسب الفئة')
            st.plotly_chart(fig, use_container_width=True)

        elif menu == "مراقبة وتغطية المخزون":
            st.title("📦 مراقبة رصيد الفروع والمستودع")
            st.dataframe(df_full[['code', 'name', 'brand', 'branch_qty', 'wh_qty', 'total_stock', 'price', 'cost']])

        elif menu == "التوصيات الذكية":
            st.title("💡 التوصيات الذكية لاتخاذ القرار")
            overstock = df_full[df_full['branch_qty'] > 300]
            st.subheader(f"🔴 أصناف ذات مخزون مرتفع جداً بالفروع ({len(overstock)} صنف)")
            st.dataframe(overstock[['code', 'name', 'brand', 'branch_qty', 'price']])
