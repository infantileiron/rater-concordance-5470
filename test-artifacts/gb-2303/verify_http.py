"""HTTP路由层验证：TestClient + SQLite + mock Redis，覆盖区间设置的请求/响应。"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from src.config.database import Base, Session, engine  # noqa: E402
from src.models import AgreementRun, AgreementStudy, RatingDataset, RatingScale, User  # noqa: E402
from src.utils.security import hash_password, token  # noqa: E402

failures = []


def check(name, cond):
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        failures.append(name)


Base.metadata.create_all(bind=engine)
levels = [{"code": f"L{i}", "label": str(i)} for i in range(1, 6)]
raters = ["甲", "乙"]
tasks = [{"task_id": f"T-{i}", "group": "g",
          "ratings": {r: f"L{(i + j) % 5 + 1}" for j, r in enumerate(raters)}} for i in range(30)]
with Session() as db:
    db.add(User(id="u1", email="a@x.demo", password=hash_password("Panel2026!"), role="admin"))
    db.add(RatingDataset(id="d1", name="数据", source="t.json", raters=raters, tasks=tasks, created_at="t"))
    db.add(RatingScale(id="sc1", name="标尺", levels=levels, created_at="t"))
    db.add(AgreementStudy(id="st1", name="研究", dataset_id="d1", scale_id="sc1",
                          rater_ids=raters, created_at="t"))
    db.commit()


class FakeRedis:
    def lpush(self, *a):
        return 1


from src.main import app  # noqa: E402

# 关闭lifespan里的自动seed与依赖redis的health
app.router.lifespan_context = None
client = TestClient(app)
with Session() as db:
    u = db.get(User, "u1")
    auth = {"Authorization": "Bearer " + token(u)}

with patch("src.services.runs.redis") as m:
    m.RedisError = Exception
    m.Redis.from_url.return_value = FakeRedis()
    # 1. 默认设置提交
    r = client.post("/runs", json={"study_id": "st1"}, headers=auth)
    check("默认设置创建运行200", r.status_code == 200)
    body = r.json()
    check("响应回显默认设置", (body["confidence_level"], body["resamples"], body["seed"]) == (0.95, 1000, 20261112))
    # 2. 自定义设置
    r2 = client.post("/runs", json={"study_id": "st1", "confidence_level": 0.99,
                                    "resamples": 250, "seed": 123}, headers=auth)
    check("自定义设置创建运行200", r2.status_code == 200 and r2.json()["resamples"] == 250)
    # 3. 非法设置被422
    for bad in [{"resamples": 50}, {"seed": -5}, {"confidence_level": 0.1}, {"resamples": 99999}]:
        rr = client.post("/runs", json={"study_id": "st1", **bad}, headers=auth)
        check(f"非法设置422: {bad}", rr.status_code == 422)
    # 4. 无鉴权401/403
    check("无token拒绝", client.post("/runs", json={"study_id": "st1"}).status_code in (401, 403))

# 5. 运行详情保留设置字段
rid = body["id"]
detail = client.get(f"/runs/{rid}", headers=auth)
check("运行详情含设置", detail.status_code == 200 and detail.json()["seed"] == 20261112)

# 6. 历史运行（三列NULL）序列化不报错且字段为null
with Session() as db:
    db.add(AgreementRun(id="legacy", study_id="st1", status="completed",
                        result={"pairs": [], "kendall": {"value": None}}, error="",
                        confidence_level=None, resamples=None, seed=None, created_at="t"))
    db.commit()
legacy = client.get("/runs/legacy", headers=auth).json()
check("历史运行设置字段为null", legacy["confidence_level"] is None and legacy["resamples"] is None)

print(f"\n{len(failures)} failed")
sys.exit(1 if failures else 0)
