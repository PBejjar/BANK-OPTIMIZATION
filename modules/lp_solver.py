import numpy as np
import pulp
import sqlite3
import pandas as pd
import math # استفاده از کتابخانه استاندارد ریاضی پایتون برای حل ارور فاکتوریل

class BranchAllocationSolver:
    """
    ماژول صنعتی تخصیص بهینه پرسنل بر مبنای تئوری صف (M/M/c) 
    و مدل‌سازی برنامه‌ریزی ریاضی عدد صحیح مختلط (MILP)
    """
    def __init__(self, db_path="data/bank_system.db"):
        self.db_path = db_path

    def calculate_minimum_tellers_queue(self, lambda_arr, mu_serv, max_wait_time=5.0):
        """
        محاسبه حداقل تعداد باجه مورد نیاز (c) با تئوری صف M/M/c
        به طوری که میانگین زمان انتظار در صف کمتر از آستانه مجاز باشد.
        """
        if lambda_arr == 0 or mu_serv == 0:
            return 1
            
        # نرخ ورود باید کمتر از ظرفیت سرویس‌دهی کل باشد (c * mu > lambda)
        c = int(np.ceil(lambda_arr / mu_serv))
        if c <= 0:
            c = 1
            
        while True:
            rho = lambda_arr / (c * mu_serv)
            if rho >= 1.0:
                c += 1
                continue
            
            # محاسبه احتمال خالی بودن سیستم (P0) با استفاده از math.factorial
            sum_terms = sum([( (lambda_arr / mu_serv) ** n ) / math.factorial(n) for n in range(c)])
            last_term = ((lambda_arr / mu_serv) ** c) / (math.factorial(c) * (1 - rho))
            p0 = 1.0 / (sum_terms + last_term)
            
            # محاسبه میانگین زمان انتظار در صف (Wq)
            lq = (p0 * ((lambda_arr / mu_serv) ** c) * rho) / (math.factorial(c) * ((1 - rho) ** 2))
            wq = (lq / lambda_arr) * 60  # تبدیل به دقیقه
            
            if wq <= max_wait_time:
                break
            c += 1
            if c > 20:  # لایه محافظتی جلوگیری از لوپ بی‌نهایت
                break
        return c

    def solve_allocation(self, budget_multiplier=1.0):
        """
        حل مدل ریاضی MILP جهت تخصیص بهینه انواع پرسنل به شعب مختلف
        با هدف بیشینه‌سازی بهره‌وری کل تحت محدودیت‌های پویای بودجه و صف
        """
        conn = sqlite3.connect(self.db_path)
        
        # خواندن داده‌ها از دیتابیس SQL
        df_branches = pd.read_sql_query("SELECT * FROM branches", conn)
        df_employees = pd.read_sql_query("SELECT * FROM employees", conn)
        conn.close()

        if df_branches.empty or df_employees.empty:
            return {"status": "Infeasible", "msg": "پایگاه داده خالی است."}

        # تعریف پارامترهای مدل ریاضی
        branches = df_branches['branch_id'].tolist()
        roles = ['Teller', 'Credit_Analyst', 'Branch_Manager']
        
        # متوسط حقوق رده‌های شغلی
        salary_map = df_employees.groupby('role')['salary'].mean().to_dict()
        for r in roles:
            if r not in salary_map:
                salary_map[r] = 10000.0  # مقدار پیش‌فرض در صورت عدم وجود داده

        # تعریف مسئله فرموله‌شده بیشینه‌سازی بهره‌وری
        prob = pulp.LpProblem("Multi_Branch_Resource_Allocation", pulp.LpMaximize)

        # متغیرهای تصمیم: تعداد پرسنل از نقش r در شعبه b (عدد صحیح غیرمنفی)
        x = pulp.LpVariable.dicts("Alloc", ((b, r) for b in branches for r in roles), lowBound=0, cat='Integer')

        # ۱. تابع هدف: بیشینه‌سازی بهره‌وری کل شبکه بانکی
        prob += pulp.lpSum(
            x[b, r] * (df_branches.loc[df_branches['branch_id'] == b, 'daily_transactions'].values[0] / 1000.0) * 
            (1.5 if r == 'Teller' else (2.0 if r == 'Credit_Analyst' else 3.0))
            for b in branches for r in roles
        )

        # اعمال محدودیت‌های مسئله (Constraints)
        for _, row in df_branches.iterrows():
            b = row['branch_id']
            
            # الف) محدودیت بودجه اختصاصی هر شعبه بر اساس ظرفیت مالی
            branch_budget = row['budget'] * budget_multiplier
            prob += pulp.lpSum(x[b, r] * salary_map[r] for r in roles) <= branch_budget

            # ب) تعیین حداقل تحویل‌دار پویا مبتنی بر خروجی تئوری صف (M/M/c)
            lambda_arr = row.get('lambda_arrival', row['daily_transactions'] / 8.0) # تخمین ساعتی
            mu_serv = row.get('mu_service', 15.0) # فرض خدمت‌دهی به ۱۵ مشتری در ساعت توسط هر باجه
            
            c_min = self.calculate_minimum_tellers_queue(lambda_arr, mu_serv, max_wait_time=8.0)
            prob += x[b, 'Teller'] >= c_min

            # ج) الزامات ساختاری نیروی انسانی شعبه
            prob += x[b, 'Credit_Analyst'] >= 1  # حداقل یک کارشناس اعتبارات
            prob += x[b, 'Branch_Manager'] == 1  # دقیقاً یک رئیس شعبه

        # حل مدل ریاضی با استفاده از پکیج محاسباتی CBC
        status = prob.solve(pulp.PULP_CBC_CMD(msg=False))
        status_str = pulp.LpStatus[status]

        if status_str == "Optimal":
            results = []
            summary = {}
            for _, row in df_branches.iterrows():
                b = row['branch_id']
                b_name = row['branch_name']
                
                allocated_tellers = int(x[b, 'Teller'].varValue)
                allocated_analysts = int(x[b, 'Credit_Analyst'].varValue)
                allocated_managers = int(x[b, 'Branch_Manager'].varValue)
                
                total_staff = allocated_tellers + allocated_analysts + allocated_managers
                spent_budget = (allocated_tellers * salary_map['Teller'] + 
                                allocated_analysts * salary_map['Credit_Analyst'] + 
                                allocated_managers * salary_map['Branch_Manager'])

                results.append({
                    "شناسه شعبه": b,
                    "نام شعبه": b_name,
                    "تعداد تحویل‌دار (Teller)": allocated_tellers,
                    "کارشناس اعتباری (Credit Analyst)": allocated_analysts,
                    "رئیس شعبه (Manager)": allocated_managers,
                    "کل پرسنل تخصیصی": total_staff,
                    "بودجه مصرف شده": f"{int(spent_budget):,}"
                })
                
                summary[b_name] = {
                    "Total_Staff": total_staff,
                    "Budget_Spent": f"{int(spent_budget):,}"
                }

            return {
                "status": "Optimal",
                "objective_value": round(pulp.value(prob.objective), 2),
                "allocation_dataframe": pd.DataFrame(results),
                "summary": summary
            }
        else:
            return {"status": "Infeasible", "msg": "مدل ریاضی در این سطح پارامترها پاسخی ندارد."}