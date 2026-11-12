"""共同完整任务整行重抽样（bootstrap）区间分析。

重抽样单位是共同完整任务整行，保留并列修正Kendall W与五级二次权重kappa的
原有算法：每次重抽样重新计算平均秩、并列修正与混淆矩阵，不做任何分布假设。
随机数使用独立random.Random(seed)，相同输入与设置逐位可复现。
"""
import hashlib
import json
import random
from itertools import combinations

from src.services.kappa import weighted_kappa
from src.services.kendall import kendall_w

DEFAULT_CONFIDENCE = 0.95
DEFAULT_RESAMPLES = 1000
DEFAULT_SEED = 20261112
MIN_RESAMPLES = 100
MAX_RESAMPLES = 10000


def quantile(values, prob):
    """线性插值分位数（与numpy默认的linear/7型分位数一致）。"""
    if not values:
        raise ValueError("分位数需要至少一个样本")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = prob * (len(ordered) - 1)
    low = int(pos)
    frac = pos - low
    if low + 1 >= len(ordered):
        return ordered[-1]
    return ordered[low] * (1 - frac) + ordered[low + 1] * frac


def make_interval(values, estimable_count, resample_count, confidence):
    """由重抽样估计序列构造百分位置信区间。

    不可估计的重抽样不计入区间样本，只单独计数；区间样本不足2个时不报告
    区间上下界，必须给出原因，不能用0或点估计替代。
    """
    if estimable_count == 0:
        return {"lower": None, "upper": None, "estimable_resamples": 0,
                "not_estimable_resamples": resample_count,
                "reason": "全部重抽样均不可估计，无区间样本（详见原始点估计的不可估计原因）"}
    if estimable_count < 2:
        return {"lower": None, "upper": None, "estimable_resamples": estimable_count,
                "not_estimable_resamples": resample_count - estimable_count,
                "reason": "区间样本仅1个，至少需要2个可估计重抽样才能计算分位数上下界"}
    alpha = (1 - confidence) / 2
    return {"lower": quantile(values, alpha), "upper": quantile(values, 1 - alpha),
            "estimable_resamples": estimable_count,
            "not_estimable_resamples": resample_count - estimable_count,
            "reason": "百分位bootstrap区间，整行重抽样重算并列修正与五级二次权重"}


def bootstrap_interval(complete, raters, confidence, resamples, seed):
    """对共同完整任务做整行有放回重抽样，返回W、各评委对kappa与均值kappa区间。"""
    n = len(complete)
    rng = random.Random(seed)
    w_values, w_ok = [], 0
    pair_combos = list(combinations(range(len(raters)), 2))
    pair_values = [[] for _ in pair_combos]
    pair_ok = [0] * len(pair_combos)
    mean_values, mean_ok = [], 0
    for _ in range(resamples):
        rows = [complete[rng.randrange(n)] for _ in range(n)]
        matrix = [t["positions"] for t in rows]
        w = kendall_w(matrix, raters)
        if w["value"] is not None:
            w_values.append(w["value"])
            w_ok += 1
        pair_estimates = []
        for pidx, (i, j) in enumerate(pair_combos):
            k = weighted_kappa([r[i] for r in matrix], [r[j] for r in matrix])
            if k["kappa"] is not None:
                pair_values[pidx].append(k["kappa"])
                pair_ok[pidx] += 1
                pair_estimates.append(k["kappa"])
        if pair_estimates:
            mean_values.append(sum(pair_estimates) / len(pair_estimates))
            mean_ok += 1
    return {
        "confidence_level": confidence,
        "resamples": resamples,
        "seed": seed,
        "method": "共同完整任务整行有放回重抽样（bootstrap），重抽样内重新计算平均秩、并列修正Kendall W与五级二次加权Cohen kappa；百分位法取区间，不做正态假设",
        "quantile_method": "线性插值分位数（numpy 7型）",
        "tasks_resampled": n,
        "kendall": make_interval(w_values, w_ok, resamples, confidence),
        "pairs": [make_interval(pair_values[i], pair_ok[i], resamples, confidence)
                  for i in range(len(pair_combos))],
        "mean_pair_kappa": make_interval(mean_values, mean_ok, resamples, confidence),
        "checksum": hashlib.sha256(json.dumps(
            {"tasks": complete, "raters": raters,
             "confidence": confidence, "resamples": resamples, "seed": seed},
            sort_keys=True).encode()).hexdigest(),
        "note": ["重抽样单位是共同完整任务整行，缺评分任务不进入重抽样池，与点估计共用同一分母。",
                 "每次重抽样重新计算并列平均秩与五级二次权重，区间继承并列修正与权重口径。",
                 "不可估计的重抽样（如重抽样后秩无变异、期望分歧为0）单独计数，不计入区间样本。",
                 "可估计重抽样少于2个时不给出上下界并说明原因，不以0或点估计替代。",
                 "区间刻画重抽样不确定性，不是显著性检验，也不自动判定评委优劣或人员决策。"],
    }
