import {useState} from 'react';
import type {Workspace} from '../stores/workspace';
import {PageHeading} from '../components/common/PageHeading';
import {Notice} from '../components/common/Notice';
import {Empty} from '../components/common/Empty';
import {Status} from '../components/common/Status';
import {Ruler} from '../components/Ruler';
import {PairTable} from '../components/PairTable';
import {ConfusionMatrix} from '../components/ConfusionMatrix';
import {TaskDisagreements} from '../components/TaskDisagreements';
import {RankProfile} from '../components/RankProfile';
import {IntervalPanel} from '../components/IntervalPanel';
import {number,confidencePct,intervalText} from '../utils/format';

export function Results({data}:{data:Workspace}){
 const [selected,setSelected]=useState(''),[pairIndex,setPairIndex]=useState(0);
 const run=data.runs.find(r=>r.id===selected)||data.runs[0];
 const pair=run?.result?.pairs?.[pairIndex]||run?.result?.pairs?.[0];
 return <>
  <PageHeading label="05 / AGREEMENT EVIDENCE" title="排序协调与等级一致，分别核对。">W不替代kappa，等级同分也不替代分母核查。<br/>不可估计项显示原因，不当成0或1。</PageHeading>
  <div className="run-selector"><label>计算记录<select aria-label="选择计算记录" value={run?.id||''} onChange={e=>{setSelected(e.target.value);setPairIndex(0)}}>{data.runs.map(r=><option key={r.id} value={r.id}>{data.studies.find(s=>s.id===r.study_id)?.name} · {r.created_at.slice(11,19)}</option>)}</select></label>{run&&<Status value={run.status}/>}</div>
  {!run?<Empty>先锁定标尺和评委组合，再运行后台计算。</Empty>:run.status!=='completed'?<Notice error={run.status==='failed'}>{run.status==='failed'?run.error:'独立worker正在计算，页面会自动刷新。'}</Notice>:<>
   {!run.result.interval&&<Notice>该运行创建于区间分析升级前，保留原有点估计结果；新建运行可配置置信水平、重抽样次数与随机种子，归档CSV同样兼容旧格式。</Notice>}
   <section className="paper">
    <div className="section-heading"><h2>共同分母与排序协调</h2><span>{run.result.raters.length}名评委 / 5级有序标尺{run.result.interval&&` / ${confidencePct(run.result.interval.confidence_level)}区间 · ${run.result.interval.resamples}次重抽样`}</span></div>
    <div className="result-metrics">
     <div><small>Kendall W{run.result.interval&&`（${confidencePct(run.result.interval.confidence_level)}区间）`}</small><b>{number(run.result.kendall.value)}</b>{run.result.interval&&<em>{intervalText(run.result.interval.kendall)}{run.result.interval.kendall.lower==null&&' · '+run.result.interval.kendall.reason}</em>}</div>
     <div><small>完整任务 / 原始任务</small><b>{run.result.tasks_complete}<i> / {run.result.tasks_total}</i></b></div>
     <div><small>整行隔离</small><b>{run.result.tasks_isolated}<i>项</i></b></div>
     <div><small>成对κ均值{run.result.interval&&`（${confidencePct(run.result.interval.confidence_level)}区间）`}</small><b>{number(run.result.mean_pair_kappa)}</b><em>可估计{run.result.estimable_pairs}对{run.result.interval&&(run.result.interval.mean_pair_kappa.lower==null?' · '+run.result.interval.mean_pair_kappa.reason:' · '+intervalText(run.result.interval.mean_pair_kappa))}</em></div>
    </div>
    <Ruler value={run.result.kendall.value}/>
    <p className="caption">{run.result.kendall.reason}；ties修正和={run.result.kendall.tie_correction}，实际分母={run.result.kendall.denominator}。</p>
    <PairTable pairs={run.result.pairs} interval={run.result.interval}/>
   </section>
   {run.result.interval&&<IntervalPanel interval={run.result.interval} pairs={run.result.pairs}/>}
   <div className="evidence-grid">
    <section className="paper"><div className="section-heading"><h2>五级评分混淆矩阵</h2><select aria-label="选择评委对" value={Math.min(pairIndex,run.result.pairs.length-1)} onChange={e=>setPairIndex(+e.target.value)}>{run.result.pairs.map((p,i)=><option key={i} value={i}>{p.rater_a} × {p.rater_b}</option>)}</select></div>{pair&&<ConfusionMatrix pair={pair} levels={run.result.levels}/>}</section>
    <aside className="definition-note"><span className="eyebrow">WEIGHTED DISAGREEMENT</span><h2>序号之差，<br/>与标签数值无关。</h2><p>第1级到第5级的二次距离为1，第1级到第2级为1/16。类别代码即使写成1、3、10、50、100，距离仍按五个位置计算。</p><p>κ = 1 − 观测分歧 / 期望分歧。期望分歧为0时不可估计。</p></aside>
   </div>
   <section className="paper"><h2>各评委的任务平均秩</h2>{run.result.rank_profile.length?<RankProfile result={run.result}/>:<Notice>完整任务不足，无法绘制任务秩。请核查隔离清单。</Notice>}</section>
   <section className="paper"><h2>优先复核的分歧任务</h2><TaskDisagreements rows={run.result.disagreements} raters={run.result.raters} levels={run.result.levels}/><p className="caption">按平均成对二次距离从大到小，预览前20项完整任务。分歧是讨论线索，不自动判断评委优劣。</p></section>
   <section className="paper"><h2>缺评分隔离清单</h2>{run.result.isolated.length?<div className="table-scroll"><table><thead><tr><th>任务</th><th>缺评分评委</th><th>处理原因</th></tr></thead><tbody>{run.result.isolated.map(t=><tr key={t.task_id}><td>{t.task_id}</td><td>{t.missing_raters.join('、')}</td><td>{t.reason}</td></tr>)}</tbody></table></div>:<Notice>所选评委的全部任务完整，无任务被隔离。</Notice>}</section>
   <aside className="assumptions"><h2>解释边界</h2>{run.result.assumptions.map((s,i)=><p key={s}><b>0{i+1}</b>{s}</p>)}<small>输入校验码 {run.result.checksum.slice(0,24)}</small>{run.result.interval&&<small>区间校验码 {run.result.interval.checksum?run.result.interval.checksum.slice(0,24):'不可用'} · 种子{run.result.interval.seed}</small>}</aside>
  </>}
 </>;
}
