import numpy as np
import pandas as pd

class BankGeneticScheduler:
    """
    موتور الگوریتم ژنتیک هوشمند جهت زمان‌بندی بهینه شیفت‌های کاری پرسنل 
    با در نظر گرفتن محدودیت خستگی و جریمه نقض قوانین کار
    """
    def __init__(self, num_employees=10, days=7, population_size=40, generations=50, mutation_rate=0.15):
        self.num_employees = num_employees
        self.days = days
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        # شیفت‌ها: 0 = استراحت، 1 = شیفت صبح، 2 = شیفت عصر
        self.shifts = [0, 1, 2] 

    def calculate_fitness(self, chromosome):
        """
        ارزیابی برازش بر اساس پایداری فیزیکی و قوانین کار:
        ۱. جریمه شدید برای شیفت عصر بلافاصله قبل از شیفت صبح فردا (خستگی مفرط)
        ۲. توزیع عادلانه ساعات کاری بین پرسنل
        """
        penalties = 0
        total_hours = np.zeros(self.num_employees)
        
        for i in range(self.num_employees):
            emp_schedule = chromosome[i, :]
            for d in range(self.days):
                # قانون ۱: اگر شیفت عصر (2) باشد، فردا نباید شیفت صبح (1) باشد
                if d < self.days - 1:
                    if emp_schedule[d] == 2 and emp_schedule[d+1] == 1:
                        penalties += 15  # جریمه سنگین نقض استراحت بین شیفت
                
                # ثبت ساعت کاری (هر شیفت کاری معادل ۸ ساعت)
                if emp_schedule[d] in [1, 2]:
                    total_hours[i] += 8

            # قانون ۲: جریمه اضافه کار غیرمجاز (بیش از ۴۴ ساعت در هفته)
            if total_hours[i] > 44:
                penalties += (total_hours[i] - 44) * 2

        # محاسبه انحراف معیار جهت عدالت در توزیع شیفت‌ها
        fairness_penalty = np.std(total_hours) * 1.5
        
        # امتیاز نهایی برازش (هرچه مجازات کمتر، برازش بالاتر)
        raw_score = 1000 - (penalties + fairness_penalty)
        return max(10, round(raw_score / 10, 2))

    def run_genetic(self):
        """
        اجرای لوپ تکاملی تولید نسل‌ها، تقاطع تک‌نقطه‌ای و جهش
        """
        # ایجاد جمعیت اولیه تصادفی
        population = [
            np.random.choice(self.shifts, size=(self.num_employees, self.days))
            for _ in range(self.population_size)
        ]
        
        best_fitness = 0
        best_individual = None
        
        for gen in range(self.generations):
            # ارزیابی برازش تک‌تک کروموزوم‌ها
            fitness_scores = [self.calculate_fitness(ind) for ind in population]
            
            # ذخیره بهترین پاسخ نسل
            max_idx = np.argmax(fitness_scores)
            if fitness_scores[max_idx] > best_fitness:
                best_fitness = fitness_scores[max_idx]
                best_individual = population[max_idx].copy()
            
            # مکانیزم انتخاب چرخ رولت (Roulette Wheel Selection)
            probs = np.array(fitness_scores) / sum(fitness_scores)
            selected_indices = np.random.choice(range(self.population_size), size=self.population_size, p=probs)
            population = [population[idx] for idx in selected_indices]
            
            # عملگر تقاطع (Crossover)
            for i in range(0, self.population_size, 2):
                if np.random.rand() < 0.8:  # نرخ تقاطع ۸۰٪
                    crossover_point = np.random.randint(1, self.days)
                    # جابجایی برنامه‌ها از نقطه برش به بعد
                    temp = population[i][:, crossover_point:].copy()
                    population[i][:, crossover_point:] = population[i+1][:, crossover_point:]
                    population[i+1][:, crossover_point:] = temp
            
            # عملگر جهش (Mutation)
            for ind in population:
                if np.random.rand() < self.mutation_rate:
                    row = np.random.randint(0, self.num_employees)
                    col = np.random.randint(0, self.days)
                    ind[row, col] = np.random.choice(self.shifts)

        # تبدیل بهترین کروموزوم یافت‌شده به دیتافریم شکیل جهت نمایش در UI
        days_names = [f"روز {i+1}" for i in range(self.days)]
        emp_names = [f"کارمند {i+1}" for i in range(self.num_employees)]
        
        shift_desc = {0: "❌ استراحت", 1: "☀️ شیفت صبح", 2: "🌙 شیفت عصر"}
        string_schedule = np.vectorize(shift_desc.get)(best_individual)
        
        df_result = pd.DataFrame(string_schedule, columns=days_names, index=emp_names)
        return {
            "fitness": best_fitness,
            "df": df_result
        }