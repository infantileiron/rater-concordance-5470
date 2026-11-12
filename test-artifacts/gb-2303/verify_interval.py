"""区间分析升级的独立验证脚本（仅标准库，python -I 运行）。

覆盖：
1. 相同输入/设置两次运行逐位可复现；换种子结果可变化；
2. 区间与点估计共用共同完整任务分母，重抽样数与不可估计计数守恒；
3. 并列修正与五级二次权重在每次重抽样内被重新计算（对比全常量输入的null处理）；
4. 完整任务不足2个时全部重抽样记为不可估计并给原因；
5. 历史调用analyze(tasks,raters,levels)无interval键，原结果结构不变；
6. 归档CSV：新运行含区间列，历史结果保持原10列；
7. 分位数线性插值与numpy 7型定义手工核对；
8. 不同置信水平的区间宽度关系；
9. 缺评分任务隔离且不进入重抽样池。
"""
import csv
import io
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from src.services.analysis import analyze  # noqa: E402
from src.services.interval import quantile  # noqa: E402
from src.services.reports import export_rows, BASE_COLS, INTERVAL_COLS  # noqa: E402

LEVELS = [{"code": f"L{i}", "label": str(i)} for i in range(1, 6)]
RATERS = ["甲", "乙", "丙"]
OPTIONS = {"confidence_level": 0.9, "resamples": 500, "seed": 42}


def make_tasks(n, seed=7):
    rng = random.Random(seed)
    tasks = []
    for i in range(n):
        base = rng.randint(0, 4)
        ratings = {}
        for r in RATERS:
            shift = rng.choice([-1, 0, 0, 1])
            ratings[r] = f"L{max(1, min(5, base + shift + 1))}"
        tasks.append({"task_id": f"T-{i+1:03}", "group": "g", "ratings": ratings})
    return tasks


def check(name, cond):
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        check.failed += 1


check.failed = 0

# 1. 可复现性：同设置两次结果完全一致
tasks = make_tasks(40)
r1 = analyze(tasks, RATERS, LEVELS, OPTIONS)
r2 = analyze(tasks, RATERS, LEVELS, OPTIONS)
check("相同输入与设置结果逐位可复现", r1["interval"] == r2["interval"])

# 换种子应改变重抽样序列
r3 = analyze(tasks, RATERS, LEVELS, {**OPTIONS, "seed": 99})
check("换随机种子产生不同区间", r1["interval"]["kendall"] != r3["interval"]["kendall"])

# 2. 计数守恒：每类指标 可估计+不可估计 == 重抽样次数
iv = r1["interval"]
for key in ("kendall", "mean_pair_kappa"):
    block = iv[key]
    check(f"{key} 重抽样计数守恒",
          block["estimable_resamples"] + block["not_estimable_resamples"] == 500)
for idx, block in enumerate(iv["pairs"]):
    check(f"pair[{idx}] 重抽样计数守恒",
          block["estimable_resamples"] + block["not_estimable_resamples"] == 500)
check("重抽样池等于共同完整任务数", iv["tasks_resampled"] == r1["tasks_complete"])
check("评委对区间数与点估计配对数一致", len(iv["pairs"]) == len(r1["pairs"]))

# 3. 区间界序与配置回显
for block in [iv["kendall"], iv["mean_pair_kappa"], *iv["pairs"]]:
    if block["lower"] is not None:
        check("区间下界不大于上界", block["lower"] <= block["upper"])
check("置信水平/次数/种子被记录",
      iv["confidence_level"] == 0.9 and iv["resamples"] == 500 and iv["seed"] == 42)

# 4. 全常量输入：点估计为null，重抽样全部不可估计并单独计数、说明原因
const_tasks = [{"task_id": f"C-{i}", "group": "", "ratings": {r: "L3" for r in RATERS}} for i in range(10)]
rc = analyze(const_tasks, RATERS, LEVELS, OPTIONS)
check("全常量W点估计不可估计", rc["kendall"]["value"] is None)
check("全常量W重抽样全部不可估计",
      rc["interval"]["kendall"]["estimable_resamples"] == 0
      and rc["interval"]["kendall"]["not_estimable_resamples"] == 500
      and rc["interval"]["kendall"]["lower"] is None and rc["interval"]["kendall"]["reason"])
check("全常量kappa重抽样全部不可估计",
      all(p["estimable_resamples"] == 0 and p["lower"] is None and p["reason"]
          for p in rc["interval"]["pairs"]))

# 5. 完整任务不足2个：不进行重抽样，全部记不可估计并说明原因
one_task = [{"task_id": "O-1", "group": "", "ratings": {r: f"L{i+1}" for i, r in enumerate(RATERS)}}]
ro = analyze(one_task, RATERS, LEVELS, OPTIONS)
check("单任务点估计W不可估计", ro["kendall"]["value"] is None)
check("单任务区间跳过重抽样且计数守恒",
      ro["interval"]["tasks_resampled"] == 1
      and ro["interval"]["kendall"]["not_estimable_resamples"] == 500
      and ro["interval"]["kendall"]["lower"] is None
      and "少于2" in ro["interval"]["kendall"]["reason"])

# 6. 历史兼容：不传设置时无interval键，结构与升级前一致
legacy = analyze(tasks, RATERS, LEVELS)
check("旧调用无interval键", "interval" not in legacy)
check("旧调用点估计字段保留", all(k in legacy for k in
      ("kendall", "pairs", "mean_pair_kappa", "checksum", "assumptions")))

# 7. 归档CSV：新运行有区间列且可被csv解析；历史结果保持原10列
cols_new, rows_new = export_rows(r1)
check("新归档包含全部区间列", cols_new == BASE_COLS + INTERVAL_COLS and len(rows_new) == len(r1["pairs"]))
buf = io.StringIO()
writer = csv.DictWriter(buf, cols_new)
writer.writeheader()
writer.writerow(rows_new[0])
parsed = list(csv.DictReader(io.StringIO(buf.getvalue())))
check("新归档CSV可解析且含种子与校验码",
      parsed[0]["bootstrap_seed"] == "42" and len(parsed[0]["interval_checksum"]) == 64)
cols_old, _ = export_rows(legacy)
check("历史归档保持原10列", cols_old == BASE_COLS and len(cols_old) == 10)
check("历史归档无任何区间列", not any("ci_" in c or "bootstrap" in c for c in cols_old))

# 8. 分位数手工核对（numpy linear/7型）
check("单值分位数", quantile([0.4], 0.025) == 0.4)
vals = list(range(10))  # p=0.25 -> 位置2.25；p=0.975 -> 位置8.775
check("分位数线性插值低端", abs(quantile(vals, 0.25) - 2.25) < 1e-12)
check("分位数线性插值高端", abs(quantile(vals, 0.975) - 8.775) < 1e-12)

# 9. 同种子同次数下，99%区间不窄于95%区间
r95 = analyze(tasks, RATERS, LEVELS, {**OPTIONS, "confidence_level": 0.95})["interval"]
r99 = analyze(tasks, RATERS, LEVELS, {**OPTIONS, "confidence_level": 0.99})["interval"]
w95 = r95["kendall"]["upper"] - r95["kendall"]["lower"]
w99 = r99["kendall"]["upper"] - r99["kendall"]["lower"]
check("99%区间不窄于95%区间（同种子同次数）", w99 >= w95)

# 10. 缺评分任务被隔离且不进入重抽样池
miss = make_tasks(10)
miss.append({"task_id": "M-1", "group": "", "ratings": {**{r: "L2" for r in RATERS}, "乙": None}})
rm = analyze(miss, RATERS, LEVELS, OPTIONS)
check("缺评分整行隔离", rm["tasks_isolated"] == 1 and rm["tasks_complete"] == 10)
check("重抽样池不含隔离任务", rm["interval"]["tasks_resampled"] == 10)

print(f"\n{check.failed} failed")
sys.exit(1 if check.failed else 0)
