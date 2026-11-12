from itertools import combinations
import hashlib,json,math
from src.services.cohort import prepare
from src.services.kendall import kendall_w
from src.services.kappa import weighted_kappa
from src.services.interval import bootstrap_interval
def analyze(tasks,raters,levels,interval_options=None):
 complete,isolated=prepare(tasks,raters,levels);matrix=[t["positions"] for t in complete];pairs=[]
 for i,j in combinations(range(len(raters)),2):pairs.append({"rater_a":raters[i],"rater_b":raters[j],**weighted_kappa([r[i] for r in matrix],[r[j] for r in matrix])})
 disagreements=[]
 for task in complete:
  positions=task["positions"];distances=[(positions[i]-positions[j])**2/16 for i,j in combinations(range(len(raters)),2)]
  disagreements.append({"task_id":task["task_id"],"group":task["group"],"codes":dict(zip(raters,task["codes"])),"span":max(positions)-min(positions),"mean_pair_distance":math.fsum(distances)/len(distances)})
 disagreements.sort(key=lambda r:(-r["mean_pair_distance"],r["task_id"]))
 w=kendall_w(matrix,raters)
 estimates=[p["kappa"] for p in pairs if p["kappa"] is not None]
 result={"raters":raters,"levels":levels,"tasks_total":len(tasks),"tasks_complete":len(complete),"tasks_isolated":len(isolated),"isolated":isolated,"kendall":w,"pairs":pairs,"estimable_pairs":len(estimates),"mean_pair_kappa":math.fsum(estimates)/len(estimates) if estimates else None,"disagreements":disagreements,"rank_profile":[{"task_id":t["task_id"],"ranks":w["ranks"][i]} for i,t in enumerate(complete)] if w["ranks"] else [],"checksum":hashlib.sha256(json.dumps({"tasks":tasks,"raters":raters,"levels":levels},sort_keys=True).encode()).hexdigest(),"assumptions":["标尺是有序1至5级，代码与文字仅作类别标签；二次权重用序号位置距离，不把标签数值当连续量。","选择评委缺任一评分的任务整行隔离；W与每一个kappa配对共用完整任务分母，隔离清单可核对。","W衡量任务排序协调，不等同于原始等级绝对一致；kappa通过边际分布校正偶然一致，可能为负。","全常量秩无变异时W为null；期望分歧为0时kappa为null，不记为完美一致。少于2个完整任务不估计。","均值kappa仅是可估计评委对的描述均值，不是推断检验或自动判定标准。模拟任务评测，不用于人员录用决策。"]}
 # 区间分析为可选升级：旧调用（无设置或完整任务不足2个）不生成interval键，历史结果结构保持不变
 if interval_options is not None:
  if len(complete)<2:
   result["interval"]={"confidence_level":interval_options["confidence_level"],"resamples":interval_options["resamples"],"seed":interval_options["seed"],"method":"共同完整任务整行有放回重抽样（bootstrap）","quantile_method":"未使用（完整任务不足，未进行重抽样）","tasks_resampled":len(complete),"kendall":{"lower":None,"upper":None,"estimable_resamples":0,"not_estimable_resamples":interval_options["resamples"],"reason":"共同完整任务少于2个，无法整行重抽样，区间不可估计"},"pairs":[{"lower":None,"upper":None,"estimable_resamples":0,"not_estimable_resamples":interval_options["resamples"],"reason":"共同完整任务少于2个，无法整行重抽样，区间不可估计"} for _ in pairs],"mean_pair_kappa":{"lower":None,"upper":None,"estimable_resamples":0,"not_estimable_resamples":interval_options["resamples"],"reason":"共同完整任务少于2个，无法整行重抽样，区间不可估计"},"checksum":None,"note":["完整任务少于2个时不进行重抽样，全部重抽样按不可估计单独计数。"]}
  else:result["interval"]=bootstrap_interval(complete,raters,interval_options["confidence_level"],interval_options["resamples"],interval_options["seed"])
 return result
