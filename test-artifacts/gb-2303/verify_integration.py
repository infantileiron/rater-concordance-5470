"""端到端集成验证：SQLite内存库 + 假Redis队列，走真实服务层与worker.execute。

验证：
- 建表包含三个新区间设置列，且可空（历史口径）；
- runs.create持久化设置，worker.execute产出含interval的结果，同设置可复现；
- 模拟历史运行（三列NULL）重算时只做点估计，无interval键；
- 归档导出新运行含区间列、历史运行保持原10列；
- Pydantic入参边界校验。
"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from src.config.database import Base, Session, engine  # noqa: E402
from src.models import (AgreementRun, AgreementStudy, RatingDataset,  # noqa: E402
                        RatingScale, PanelReview, Report)
from src.services import runs as run_service  # noqa: E402
from src.services import reports as report_service  # noqa: E402
from src.schemas.run import RunInput  # noqa: E402
from src.schemas.report import ReportInput  # noqa: E402

failures = []


def check(name, cond):
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        failures.append(name)


# 复用项目Session（其engine由DATABASE_URL环境变量指向临时SQLite文件）
Base.metadata.create_all(bind=engine)


class FakeRedis:
    def lpush(self, *a):
        return 1


# worker模块导入时会执行恢复循环与消费死循环：先建表、mock redis与心跳，
# 加载源码并剥掉模块级while消费循环，只保留execute函数用于测试
import importlib.util  # noqa: E402
from pathlib import Path as _Path  # noqa: E402
from unittest.mock import patch  # noqa: E402

worker_path = _Path(__file__).resolve().parents[2] / "backend" / "src" / "worker.py"
worker_src = worker_path.read_text(encoding="utf-8")
marker = "while True:"
head, _, _ = worker_src.partition(marker)
spec = importlib.util.spec_from_loader("test_worker", loader=None)
worker_module = importlib.util.module_from_spec(spec)
with patch("redis.Redis.from_url", return_value=FakeRedis()), \
     patch("pathlib.Path.touch"):
    exec(compile(head, str(worker_path), "exec"), worker_module.__dict__)
execute = worker_module.execute

# 1. 表结构含三新列且可空
table = Base.metadata.tables["agreement_runs"]
cols = {c.name: c for c in table.columns}
for c in ("confidence_level", "resamples", "seed"):
    check(f"列存在且可空: {c}", c in cols and cols[c].nullable)

# 准备数据
levels = [{"code": f"L{i}", "label": str(i)} for i in range(1, 6)]
raters = ["甲", "乙", "丙"]
import random
rng = random.Random(101)
tasks = [{"task_id": f"T-{i:03}", "group": "g",
          "ratings": {r: f"L{max(1, min(5, rng.randint(1, 5) + rng.choice([-1, 0, 1])))}" for r in raters}}
         for i in range(50)]

with Session() as db:
    db.add(RatingDataset(id="d1", name="数据集", source="t.json", raters=raters, tasks=tasks, created_at="t"))
    db.add(RatingScale(id="sc1", name="标尺", levels=levels, created_at="t"))
    db.add(AgreementStudy(id="st1", name="研究一", dataset_id="d1", scale_id="sc1",
                          rater_ids=raters, created_at="t"))
    db.commit()

    class FakeRedis:
        def lpush(self, *a):
            return 1

    # 2. 新运行：设置持久化 + worker计算 + 可复现
    payload = RunInput(study_id="st1", confidence_level=0.9, resamples=300, seed=77)
    with patch("src.services.runs.redis") as m:
        m.RedisError = Exception
        m.Redis.from_url.return_value = FakeRedis()
        row = run_service.create(db, payload)
    run_id = row["id"]
    check("设置已持久化", (row["confidence_level"], row["resamples"], row["seed"]) == (0.9, 300, 77))
    execute(run_id)
    db.expire_all()
    first = db.get(AgreementRun, run_id)
    check("worker完成且含interval", first.status == "completed" and "interval" in first.result)
    iv1 = first.result["interval"]
    check("interval回显设置", (iv1["confidence_level"], iv1["resamples"], iv1["seed"]) == (0.9, 300, 77))

    # 再跑一次同设置，结果逐位相同
    with patch("src.services.runs.redis") as m:
        m.RedisError = Exception
        m.Redis.from_url.return_value = FakeRedis()
        row2 = run_service.create(db, payload)
    execute(row2["id"])
    db.expire_all()
    second = db.get(AgreementRun, row2["id"])
    check("同设置两次worker结果可复现", second.result["interval"] == iv1)

    # 3. 历史运行：三列NULL，worker只做点估计
    legacy = AgreementRun(id="legacy-run", study_id="st1", status="queued", result={}, error="",
                          confidence_level=None, resamples=None, seed=None, created_at="t")
    db.add(legacy)
    db.commit()
    execute("legacy-run")
    db.expire_all()  # worker在独立会话提交，本会话身份映射需过期后重新加载
    legacy = db.get(AgreementRun, "legacy-run")
    check("历史运行完成且无interval键", legacy.status == "completed" and "interval" not in legacy.result)
    check("历史运行点估计完整", all(k in legacy.result for k in ("kendall", "pairs", "checksum")))

    # 4. 归档导出：新运行有区间列；历史运行保持原10列
    db.add(PanelReview(id="rv1", run_id=run_id, note="依据充分" * 3, decision="accepted",
                       author="a@x", created_at="t"))
    db.add(PanelReview(id="rv2", run_id="legacy-run", note="依据充分" * 3, decision="accepted",
                       author="a@x", created_at="t"))
    db.commit()
    rep_new = report_service.create(db, ReportInput(run_id=run_id, title="新归档"),
                                    {"email": "admin@x"})
    rep_old = report_service.create(db, ReportInput(run_id="legacy-run", title="旧归档"),
                                    {"email": "admin@x"})
    csv_new = report_service.export(db, rep_new["id"])
    csv_old = report_service.export(db, rep_old["id"])
    header_new = csv_new.lstrip("﻿").splitlines()[0].split(",")
    header_old = csv_old.lstrip("﻿").splitlines()[0].split(",")
    check("新归档含区间12列", len(header_new) == 22 and "bootstrap_seed" in header_new
          and "interval_checksum" in header_new and "kappa_ci_lower" in header_new)
    check("历史归档保持原10列", header_old == ["rater_a", "rater_b", "complete_tasks", "isolated_tasks",
          "kendall_w", "kappa", "observed_disagreement", "expected_disagreement",
          "exact_agreement", "reason"])
    check("新归档数据行数=评委对数", len(csv_new.splitlines()) == 1 + len(first.result["pairs"]))

    # 5. 重复归档被拒
    try:
        report_service.create(db, ReportInput(run_id=run_id, title="重复"), {"email": "admin@x"})
        check("重复归档被拒绝", False)
    except Exception:
        check("重复归档被拒绝", True)

# 6. schema边界
for bad in [dict(confidence_level=0.49), dict(confidence_level=1.0), dict(resamples=99),
            dict(resamples=10001), dict(seed=-1), dict(seed=2147483648)]:
    try:
        RunInput(study_id="st1", **bad)
        check(f"非法入参被拒: {bad}", False)
    except Exception:
        check(f"非法入参被拒: {bad}", True)
for ok in [dict(confidence_level=0.5), dict(confidence_level=0.99), dict(resamples=100),
           dict(resamples=10000), dict(seed=0), dict(seed=2147483647)]:
    try:
        RunInput(study_id="st1", **ok)
        check(f"边界合法入参通过: {ok}", True)
    except Exception:
        check(f"边界合法入参通过: {ok}", False)

print(f"\n{len(failures)} failed")
sys.exit(1 if failures else 0)
