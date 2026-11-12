import uuid,csv,io
from src.utils.csv import safe_cell
BASE_COLS=["rater_a","rater_b","complete_tasks","isolated_tasks","kendall_w","kappa","observed_disagreement","expected_disagreement","exact_agreement","reason"]
INTERVAL_COLS=["kendall_w_ci_lower","kendall_w_ci_upper","mean_pair_kappa_ci_lower","mean_pair_kappa_ci_upper","kappa_ci_lower","kappa_ci_upper","kappa_estimable_resamples","kappa_not_estimable_resamples","confidence_level","bootstrap_resamples","bootstrap_seed","interval_checksum"]
def export_rows(result):
 """把运行结果展开为CSV列与行；无interval键的历史结果只返回原始十列。"""
 interval=result.get("interval");cols=BASE_COLS+INTERVAL_COLS if interval else BASE_COLS;rows=[]
 for idx,p in enumerate(result["pairs"]):
  row={"rater_a":safe_cell(p["rater_a"]),"rater_b":safe_cell(p["rater_b"]),"complete_tasks":result["tasks_complete"],"isolated_tasks":result["tasks_isolated"],"kendall_w":result["kendall"]["value"],**{k:p[k] for k in ("kappa","observed_disagreement","expected_disagreement","exact_agreement","reason")}}
  if interval:
   pci=interval["pairs"][idx] if idx<len(interval["pairs"]) else {}
   row.update({"kendall_w_ci_lower":interval["kendall"]["lower"],"kendall_w_ci_upper":interval["kendall"]["upper"],"mean_pair_kappa_ci_lower":interval["mean_pair_kappa"]["lower"],"mean_pair_kappa_ci_upper":interval["mean_pair_kappa"]["upper"],"kappa_ci_lower":pci.get("lower"),"kappa_ci_upper":pci.get("upper"),"kappa_estimable_resamples":pci.get("estimable_resamples"),"kappa_not_estimable_resamples":pci.get("not_estimable_resamples"),"confidence_level":interval["confidence_level"],"bootstrap_resamples":interval["resamples"],"bootstrap_seed":interval["seed"],"interval_checksum":interval.get("checksum")})
  rows.append(row)
 return cols,rows
def create(db,payload,user):
 from fastapi import HTTPException
 from sqlalchemy import select
 from src.models import Report,PanelReview
 from src.services.runs import require_completed
 from src.utils.time import now
 from src.utils.serialization import serialize
 require_completed(db,payload.run_id)
 review=db.scalar(select(PanelReview).where(PanelReview.run_id==payload.run_id).order_by(PanelReview.created_at.desc()))
 if not review or review.decision!="accepted":raise HTTPException(409,"最新复核须为接受后才能归档")
 if db.scalar(select(Report).where(Report.run_id==payload.run_id)):raise HTTPException(409,"本次运行已归档")
 item=Report(id=str(uuid.uuid4()),published_by=user["email"],created_at=now(),**payload.model_dump());db.add(item);db.commit();return serialize(item)
def export(db,id):
 from fastapi import HTTPException
 from src.models import Report
 from src.services.runs import require_completed
 report=db.get(Report,id)
 if not report:raise HTTPException(404,"报告不存在")
 result=require_completed(db,report.run_id).result;buf=io.StringIO()
 cols,rows=export_rows(result)
 writer=csv.DictWriter(buf,cols);writer.writeheader()
 for row in rows:writer.writerow(row)
 return "﻿"+buf.getvalue()
