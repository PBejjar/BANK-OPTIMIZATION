import streamlit as st
import pandas as pd
import sqlite3
import os
import plotly.express as px
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.lp_solver import BranchAllocationSolver
from modules.genetic_solver import BankGeneticScheduler

# تنظیم هدر استریم‌لیت
st.set_page_config(
    page_title="سیستم یکپارچه تصمیم‌یار و بهینه‌سازی منابع بانک",
    page_icon="🏦",
    layout="wide"
)

DB_PATH = "data/bank_system.db"

# =========================================================
# مقداردهی و ساخت خودکار بانک اطلاعاتی SQLite در اولین اجرا
# =========================================================
def init_database():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # ساخت جدول پرسنل
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            employee_id TEXT PRIMARY KEY,
            role TEXT,
            salary INTEGER
        )
    """)
    
    # ساخت جدول شعب به همراه اطلاعات تئوری صف
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS branches (
            branch_id INTEGER PRIMARY KEY AUTOINCREMENT,
            branch_name TEXT,
            daily_transactions INTEGER,
            budget INTEGER,
            lambda_arrival REAL,
            mu_service REAL
        )
    """)
    
    # درج داده‌های پیش‌فرض در صورت خالی بودن دیتابیس
    cursor.execute("SELECT count(*) FROM employees")
    if cursor.fetchone()[0] == 0:
        emp_data = [
            ("EMP-101", "Teller", 12000), ("EMP-102", "Teller", 12500),
            ("EMP-103", "Teller", 11800), ("EMP-104", "Credit_Analyst", 18000),
            ("EMP-105", "Credit_Analyst", 19500), ("EMP-106", "Branch_Manager", 30000),
            ("EMP-107", "Teller", 13000), ("EMP-108", "Credit_Analyst", 17500),
            ("EMP-109", "Branch_Manager", 29000), ("EMP-110", "Teller", 12100)
        ]
        cursor.executemany("INSERT INTO employees VALUES (?, ?, ?)", emp_data)

    cursor.execute("SELECT count(*) FROM branches")
    if cursor.fetchone()[0] == 0:
        branch_data = [
            ("شعبه مرکزی", 1850, 85000, 32.5, 15.0),
            ("شعبه آزادی", 1100, 55000, 18.0, 15.0),
            ("شعبه ونک", 1450, 70000, 25.0, 15.0)
        ]
        cursor.executemany("INSERT INTO branches (branch_name, daily_transactions, budget, lambda_arrival, mu_service) VALUES (?, ?, ?, ?, ?)", branch_data)
        
    conn.commit()
    conn.close()

init_database()

# =========================================================
# پیاده‌سازی گیت احراز هویت با ساختار State مدیریت‌شده
# =========================================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_role = None

if not st.session_state.logged_in:
    st.title("🔐 پورتال جامع تصمیم‌یار بانکداری هوشمند")
    
    with st.form("secure_login_form"):
        username = st.text_input("نام کاربری")
        password = st.text_input("رمز عبور", type="password")
        role_selection = st.selectbox("سطح دسترسی سازمانی", ["رئیس بانک (مدیر ارشد)", "کارمند بانک / ناظر کیفی"])
        submit_login = st.form_submit_button("🛡️ تأیید هویت و ورود ایمن")
        
        if submit_login:
            if role_selection == "رئیس بانک (مدیر ارشد)" and username == "admin" and password == "1234":
                st.session_state.logged_in = True
                st.session_state.user_role = "admin"
                st.rerun()
            elif role_selection == "کارمند بانک / ناظر کیفی" and username == "staff" and password == "1111":
                st.session_state.logged_in = True
                st.session_state.user_role = "employee"
                st.rerun()
            else:
                st.error("❌ دسترسی غیرمجاز! مشخصات وارد شده نادرست است.")
                
    st.info("💡 **مشخصات ورود پیش‌فرض:** رئیس (`admin` / `1234`) | کارمند (`staff` / `1111`)")
    st.stop()

# سایدبار مدیریت حساب کاربر
st.sidebar.markdown(f"### 👤 سطح کاربری: { 'رئیس کل بانک' if st.session_state.user_role == 'admin' else 'کارمند سیستم' }")
if st.sidebar.button("🚪 خروج ایمن از سامانه", key="app_logout_button"):
    st.session_state.logged_in = False
    st.session_state.user_role = None
    st.rerun()

st.sidebar.markdown("---")

# استایل‌دهی مدرن CSS و فارسی‌سازی کامل راست‌چین (RTL) به همراه تراز فیلدهای عددی انگلیسی
st.markdown("""
    <link href="https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/Vazirmatn-font-face.css" rel="stylesheet" type="text/css" />
    <style>
        html, body, [data-testid="stAppViewContainer"], .main, [data-testid="stHeader"], [data-testid="stSidebar"], .stTabs {
            font-family: 'Vazirmatn', sans-serif !important;
            direction: rtl !important;
            text-align: right !important;
        }
        .stSlider, [data-testid="stWidgetLabel"], .stButton, .stTextInput, .stNumberInput, .stSelectbox, form {
            direction: rtl !important;
            text-align: right !important;
        }
        code, pre, [data-testid="stMetricValue"], [data-testid="stMetricDelta"], .stDataFrame, [data-testid="stTable"], .ltr-text, input[type="number"] {
            direction: ltr !important;
            text-align: left !important;
            font-family: monospace, sans-serif !important;
        }
    </style>
""", unsafe_allow_html=True)

st.title("🏦 سامانه یکپارچه برنامه‌ریزی ریاضی و منابع شبکه بانکی")

# =========================================================
# تفکیک پویای دسترسی تب‌ها بر اساس نقش کاربر
# =========================================================
tabs_object = []
tab_map = {}

if st.session_state.user_role == "admin":
    tab_list = [
        "🎯 ماژول برنامه‌ریزی خطی پویا & تئوری صف", 
        "🧬 زمان‌بندی هوشمند پرسنل با الگوریتم ژنتیک", 
        "📊 مرکز کنترل متمرکز و ویرایش دیتابیس بانک", 
        "🤖 دستیار ارشد تحلیلی و چت‌بات هوشمند"
    ]
    tabs_object = st.tabs(tab_list)
    tab_map = {0: tabs_object[0], 1: tabs_object[1], 2: tabs_object[2], 3: tabs_object[3]}
else:
    tab_list = [
        "📊 مانیتورینگ آنلاین شعب و شاخص‌های آماری", 
        "🤖 دستیار ارشد تحلیلی و چت‌بات هوشمند"
    ]
    tabs_object = st.tabs(tab_list)
    tab_map = {2: tabs_object[0], 3: tabs_object[1]}

# =========================================================
# پیاده‌سازی محتوای ماژولار تب‌ها
# =========================================================

# --- تب اول: مدل ریاضی LP/MILP و تئوری صف (فقط ادمین) ---
if 0 in tab_map:
    with tab_map[0]:
        st.header("🎯 بهینه‌سازی تخصیص پرسنل بر مبنای تئوری صف و مدل ریاضی")
        st.subheader("مدل تصمیم‌گیری تحقیق در عملیات پیشرفته")
        
        st.sidebar.header("⚙️ تنظیمات پویای مدل ریاضی")
        budget_mult = st.sidebar.slider("ضریب نوسان و انعطاف بودجه شعب", 0.8, 1.5, 1.1, 0.1)

        if st.button("🚀 اجرای محاسبات و حل همزمان سیستم صف و مدل MILP"):
            solver = BranchAllocationSolver(DB_PATH)
            res = solver.solve_allocation(budget_multiplier=budget_mult)
            
            if res['status'] == "Optimal":
                st.success(f"✅ مدل با موفقیت حل شد! مقدار تابع بهره‌وری هدف: {res['objective_value']:,}")
                
                # نمایش معیارهای کلیدی
                cols = st.columns(len(res['summary']))
                for col, (b_name, info) in zip(cols, res['summary'].items()):
                    with col:
                        st.metric(label=f"🏢 {b_name}", value=f"{info['Total_Staff']} پرسنل تخصیصی")
                        st.caption(f"بودجه مصرفی: {info['Budget_Spent']} واحد")
                
                st.markdown("### جدول تخصیص بهینه پرسنل کل شعب")
                st.dataframe(res['allocation_dataframe'], use_container_width=True)
            else:
                st.error("❌ خطا در حل مدل! محدوده بودجه برای پاسخ‌های تئوری صف کافی نیست. بودجه را افزایش دهید.")

# --- تب دوم: الگوریتم ژنتیک (فقط ادمین) ---
if 1 in tab_map:
    with tab_map[1]:
        st.header("🧬 زمان‌بندی پویای شیفت پرسنل با الگوریتم ژنتیک")
        st.caption("این الگوریتم با تعریف جریمه‌های هوشمند، قوانین سختی کار و عدالت در توزیع شیفت‌ها را رعایت می‌کند.")
        
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            num_emp = st.number_input("تعداد پرسنل هدف جهت برنامه‌ریزی کار", 5, 50, 12)
        with col_g2:
            gens = st.slider("تعداد کل نسل‌های فرآیند تکامل (Generations)", 20, 150, 50)
            
        if st.button("🧬 ران کردن الگوریتم ژنتیک بر بستر الگوهای همگرایی"):
            scheduler = BankGeneticScheduler(num_employees=num_emp, generations=gens)
            genetic_res = scheduler.run_genetic()
            
            st.success(f"🎯 الگوریتم با موفقیت همگرا شد. امتیاز کیفیت برازش شیفت‌بندی: {genetic_res['fitness']}%")
            st.dataframe(genetic_res['df'], use_container_width=True)

# --- تب سوم: مرکز کنترل پایگاه داده SQL (دسترسی ویرایشی فقط برای ادمین، نمایشی برای همه) ---
if 2 in tab_map:
    with tab_map[2]:
        st.header("🗄️ سیستم یکپارچه مدیریت اطلاعات شبکه بانکی (SQLite Dynamic Control)")
        
        conn = sqlite3.connect(DB_PATH)
        df_emp = pd.read_sql_query("SELECT * FROM employees", conn)
        df_br = pd.read_sql_query("SELECT * FROM branches", conn)
        conn.close()

        # بخش مدیریت اطلاعات - مخصوص ادمین
        if st.session_state.user_role == "admin":
            st.subheader("➕ مدیریت اعضای سازمان (افزودن و حذف پرسنل در لحظه)")
            col_admin_db1, col_admin_db2 = st.columns(2)
            
            with col_admin_db1:
                with st.expander("📝 افزودن نیروی انسانی جدید", expanded=False):
                    with st.form("insert_employee_sql_form"):
                        new_emp_id = st.text_input("کد کارمندی انحصاری (مثال: EMP-112)")
                        new_role = st.selectbox("رده شغلی تخصصی", ["Teller", "Credit_Analyst", "Branch_Manager"])
                        new_salary = st.number_input("حقوق ماهانه مصوب (واحد)", 10000, 50000, 15000)
                        
                        if st.form_submit_button("💾 ثبت نهایی در دیتابیس"):
                            if new_emp_id and new_emp_id not in df_emp['employee_id'].values:
                                conn = sqlite3.connect(DB_PATH)
                                cursor = conn.cursor()
                                cursor.execute("INSERT INTO employees VALUES (?, ?, ?)", (new_emp_id, new_role, new_salary))
                                conn.commit()
                                conn.close()
                                st.success("کارمند جدید افزوده شد.")
                                st.rerun()
                            else:
                                st.error("کد کارمندی از قبل در سیستم موجود است.")
                                
            with col_admin_db2:
                with st.expander("🗑️ خروج از خدمت / حذف پرسنل", expanded=False):
                    with st.form("delete_employee_sql_form"):
                        emp_to_delete = st.selectbox("کد کارمند را انتخاب کنید:", df_emp['employee_id'].tolist())
                        if st.form_submit_button("❌ حذف دائم"):
                            conn = sqlite3.connect(DB_PATH)
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM employees WHERE employee_id = ?", (emp_to_delete,))
                            conn.commit()
                            conn.close()
                            st.success("حذف با موفقیت انجام شد.")
                            st.rerun()

        # نمودارها و آمارها - مشترک برای هر دو رول
        st.markdown("---")
        st.subheader("📈 داشبورد گرافیکی وضعیت شعب و تحلیل‌های آماری")
        
        kpi_col1, kpi_col2, kpi_col3 = st.columns(3)
        with kpi_col1:
            st.metric("👥 کل پرسنل فعال", f"{len(df_emp)} نفر")
        with kpi_col2:
            st.metric("📈 کل تراکنش‌های روزانه سیستم", f"{df_br['daily_transactions'].sum():,} تراکنش")
        with kpi_col3:
            st.metric("💰 میانگین حقوق پرداختی بانک", f"{int(df_emp['salary'].mean()):,} واحد")
            
        st.markdown("### تحلیل ساختار شعب")
        fig_br = px.bar(
            df_br, 
            x="branch_name", 
            y="daily_transactions", 
            color="daily_transactions",
            title="حجم تراکنش روزانه به تفکیک شعب با ظرفیت‌سنجی صف",
            color_continuous_scale="Purples"
        )
        st.plotly_chart(fig_br, use_container_width=True)

# --- تب چهارم: چت‌بات هوشمند متصل به دیتابیس SQL (مشترک) ---
if 3 in tab_map:
    with tab_map[3]:
        st.header("🤖 چت‌بات تصمیم‌یار هوشمند مدیریت منابع")
        st.caption("این دستیار هوشمند مستقیماً به پایگاه داده SQLite متصل است و به صورت بلادرنگ گزارش و فیلتر ارائه می‌دهد.")
        
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = [
                {"role": "assistant", "content": "سلام! من مشاور تحلیلی بانک شما هستم. آماده پاسخ به سوالات شما درباره شعب، حقوق پرسنل و ظرفیت تئوری صف‌ها هستم."}
            ]

        for chat in st.session_state.chat_history:
            with st.chat_message(chat["role"]):
                st.write(chat["content"])

        if user_prompt := st.chat_input("سوال خود را تایپ کنید (مثال: شلوغ‌ترین شعبه کدام است؟)", key="chatbot_core_input"):
            st.session_state.chat_history.append({"role": "user", "content": user_prompt})
            with st.chat_message("user"):
                st.write(user_prompt)

            with st.chat_message("assistant"):
                cleaned_q = user_prompt.lower()
                
                # اتصال مستقیم به داده برای پاسخگویی بلادرنگ
                conn = sqlite3.connect(DB_PATH)
                df_emp_bot = pd.read_sql_query("SELECT * FROM employees", conn)
                df_br_bot = pd.read_sql_query("SELECT * FROM branches", conn)
                conn.close()

                # پاسخ پویای چت‌بات مبتنی بر داده‌های واقعی SQL
                if any(word in cleaned_q for word in ["شلوغ", "تراکنش", "شعب", "شعبه"]):
                    max_tx_branch = df_br_bot.loc[df_br_bot['daily_transactions'].idxmax()]
                    response_text = f"🏢 **تحلیل ترافیک شعب:** در حال حاضر شلوغ‌ترین نقطه، **{max_tx_branch['branch_name']}** با ثبت روزانه **{max_tx_branch['daily_transactions']:,}** تراکنش می‌باشد. نرخ ورود مشتری به این شعبه در ساعت برابر با **{max_tx_branch['lambda_arrival']}** است."
                
                elif any(word in cleaned_q for word in ["حقوق", "پرسنل", "کارمند", "مالی"]):
                    avg_sal = int(df_emp_bot['salary'].mean())
                    total_sal = int(df_emp_bot['salary'].sum())
                    response_text = f"💰 **گزارش امور مالی پرسنل:** مجموع حقوق پرداختی شبکه بانکی برابر با **{total_sal:,} واحد** و میانگین دستمزد پرسنل فعال معادل **{avg_sal:,} واحد** است."
                
                elif any(word in cleaned_q for word in ["صف", "تئوری صف", "سرویس"]):
                    response_text = f"📊 **تحلیل مهندسی صنایع (تئوری صف):** میانگین زمان خدمت‌دهی پیش‌فرض باجه‌ها **{df_br_bot['mu_service'].iloc[0]} مشتری در ساعت** است. نرخ‌های ورود به‌صورت لحظه‌ای برای تضمین زمان انتظار حداکثر ۵ دقیقه‌ای مشتریان پایش می‌شوند."
                
                else:
                    response_text = "🤖 متوجه سوال شما شدم. لطفاً در زمینه تحلیل آماری پرسنل، پر ترافیک‌ترین شعب بانک یا مباحث بهینه‌سازی تئوری صف بپرسید تا با مراجعه به دیتابیس دقیقاً پاسخ دهم."
                
                st.write(response_text)
                st.session_state.chat_history.append({"role": "assistant", "content": response_text})
