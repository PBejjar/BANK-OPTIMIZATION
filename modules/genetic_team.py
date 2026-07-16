# modules/genetic_team.py
import random
import pandas as pd
from typing import List, Dict, Any, Tuple

class AgileTeamGeneticSolver:
    """
    پیاده‌سازی الگوریتم ژنتیک سفارشی برای تیم‌سازی چابک با حداکثرسازی هم‌افزایی و حداقل‌سازی تعارضات
    """
    def __init__(self, employees_path: str, required_skills: List[str], team_size: int = 5):
        self.df_employees = pd.read_csv(employees_path)
        self.required_skills = required_skills
        self.team_size = team_size
        self.all_emp_ids = self.df_employees['Employee_ID'].tolist()
        
        # پیش‌پردازش دیتای کارمندان برای افزایش سرعت فرآیند تکاملی
        self.emp_data = {}
        for _, row in self.df_employees.iterrows():
            self.emp_data[row['Employee_ID']] = {
                'skills': set(row['Skills'].split(',')),
                'behavioral': row['Behavioral_Score']
            }

    def _calculate_fitness(self, chromosome: List[str]) -> float:
        """
        تابع برازش (Fitness Function):
        f = (وزن * پوشش مهارتی) - (وزن * انحراف رفتار معیار جهت کاهش تعارض)
        """
        if len(set(chromosome)) != self.team_size:  # جریمه سنگین برای کارمندان تکراری در یک تیم
            return 0.0
        
        # ۱. محاسبه هم‌افزایی مهارتی (پوشش مهارت‌های مورد نیاز پروژه)
        team_skills = set()
        for emp_id in chromosome:
            team_skills.update(self.emp_data[emp_id]['skills'])
            
        covered_skills = team_skills.intersection(set(self.required_skills))
        skills_score = len(covered_skills) / len(self.required_skills)
        
        # ۲. محاسبه پایداری تیمی و تعارضات (هرچه تفاوت امتیاز رفتاری کمتر باشد، تعارض کمتر است)
        behavioral_scores = [self.emp_data[emp_id]['behavioral'] for emp_id in chromosome]
        mean_behavioral = sum(behavioral_scores) / len(behavioral_scores)
        variance = sum((x - mean_behavioral) ** 2 for x in behavioral_scores) / len(behavioral_scores)
        conflict_penalty = variance ** 0.5  # انحراف معیار امتیاز رفتاری
        
        # تابع برازش نهایی (تلفیق دو معیار)
        fitness = (skills_score * 10.0) - (conflict_penalty * 1.5)
        return max(0.1, fitness)

    def _crossover(self, parent1: List[str], parent2: List[str]) -> Tuple[List[str], List[str]]:
        """
        اپراتور تقاطع سفارشی (Single-point Crossover همراه با اصلاح جهت عدم تکرار کارمند)
        """
        point = random.randint(1, self.team_size - 1)
        child1 = parent1[:point] + [item for item in parent2 if item not in parent1[:point]]
        child2 = parent2[:point] + [item for item in parent1 if item not in parent2[:point]]
        
        # فیکس کردن طول کروموزوم در صورت لزوم
        while len(child1) < self.team_size:
            child1.append(random.choice([x for x in self.all_emp_ids if x not in child1]))
        while len(child2) < self.team_size:
            child2.append(random.choice([x for x in self.all_emp_ids if x not in child2]))
            
        return child1[:self.team_size], child2[:self.team_size]

    def _mutate(self, chromosome: List[str], mutation_rate: float) -> List[str]:
        """
        اپراتور جهش سفارشی (تعویض یک کارمند با کارمندی دیگر خارج از تیم)
        """
        if random.random() < mutation_rate:
            idx_to_replace = random.randint(0, self.team_size - 1)
            available_pool = [x for x in self.all_emp_ids if x not in chromosome]
            if available_pool:
                chromosome[idx_to_replace] = random.choice(available_pool)
        return chromosome

    def solve(self, pop_size: int = 50, generations: int = 100, mutation_rate: float = 0.15) -> Dict[str, Any]:
        # ایجاد جمعیت اولیه تصادفی
        population = [random.sample(self.all_emp_ids, k=self.team_size) for _ in range(pop_size)]
        
        best_chromosome = None
        best_fitness = -1.0
        
        for gen in range(generations):
            # ارزیابی شایستگی‌ها
            fitness_scores = [self._calculate_fitness(chrom) for chrom in population]
            
            # ذخیره بهترین پاسخ نسل
            for i, score in enumerate(fitness_scores):
                if score > best_fitness:
                    best_fitness = score
                    best_chromosome = population[i]
            
            # چرخ رولت جهت انتخاب والدین (Selection)
            total_fit = sum(fitness_scores)
            probs = [score / total_fit for score in fitness_scores]
            
            new_population = []
            for _ in range(pop_size // 2):
                p1 = random.choices(population, weights=probs, k=1)[0]
                p2 = random.choices(population, weights=probs, k=1)[0]
                
                # اعمال تکامل و تولید فرزندان
                c1, c2 = self._crossover(p1, p2)
                c1 = self._mutate(c1, mutation_rate)
                c2 = self._mutate(c2, mutation_rate)
                
                new_population.extend([c1, c2])
                
            population = new_population

        # استخراج دیتای تیم برنده
        df_team = self.df_employees[self.df_employees['Employee_ID'].isin(best_chromosome)].copy()
        
        all_skills = set()
        for s in df_team['Skills']:
            all_skills.update(s.split(','))
            
        return {
            "best_team_ids": best_chromosome,
            "fitness": best_fitness,
            "team_dataframe": df_team,
            "skills_covered": list(all_skills.intersection(set(self.required_skills))),
            "average_behavioral": df_team['Behavioral_Score'].mean()
        }

# تست سریع ماژول
if __name__ == "__main__":
    reqs = ['Python', 'Machine_Learning', 'Agile', 'DevOps']
    solver = AgileTeamGeneticSolver('../data/mock_employees.csv', required_skills=reqs)
    res = solver.solve()
    print(f"بالاترین امتیاز شایستگی (Fitness): {res['fitness']:.2f}")
    print(f"مهارت‌های پوشش داده شده: {res['skills_covered']}")
    print(res['team_dataframe'][['Employee_ID', 'Role', 'Skills']])