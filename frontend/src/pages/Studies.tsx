import {useState} from 'react';
import type {Workspace} from '../stores/workspace';
import {PageHeading} from '../components/common/PageHeading';
import {Notice} from '../components/common/Notice';
import {Status} from '../components/common/Status';
import {create} from '../api/studies';
import {create as run} from '../api/runs';
import {useAsync} from '../hooks/useAsync';
import {date,confidencePct} from '../utils/format';

export function Studies({data,canWrite,refresh,go}:{data:Workspace;canWrite:boolean;refresh:()=>Promise<void>;go:(s:string)=>void}){
 const [name,setName]=useState(''),[datasetId,setDatasetId]=useState(''),[scaleId,setScaleId]=useState(''),[selected,setSelected]=useState<string[]|null>(null);
 const [confidenceLevel,setConfidenceLevel]=useState(0.95),[resamples,setResamples]=useState(1000),[seed,setSeed]=useState(20261112);
 const ds=data.datasets.find(d=>d.id===datasetId)||data.datasets[0];
 const raters=selected===null?ds?.raters||[]:selected;
 const task=useAsync();
 const resamplesValid=resamples>=100&&resamples<=10000;
 const seedValid=seed>=0&&seed<=2147483647;
 const intervalValid=resamplesValid&&seedValid;
 return <>
  <PageHeading label="04 / PANEL STUDY" title="选择评委，也选择共同的任务分母。">选中评委缺任一评分，整任务进入隔离清单。<br/>W与全部成对kappa使用同一组完整任务。</PageHeading>
  {canWrite&&<section className="paper"><h2>建立一致性研究</h2><form className="grid-form" onSubmit={e=>{e.preventDefault();task.execute(async()=>{await create({name,dataset_id:ds?.id,scale_id:scaleId||data.scales[0]?.id,rater_ids:raters});setName('');await refresh()})}}><label>研究名称<input aria-label="研究名称" required minLength={2} value={name} onChange={e=>setName(e.target.value)}/></label><label>盲评任务集<select aria-label="研究盲评集" value={ds?.id||''} onChange={e=>{setDatasetId(e.target.value);setSelected(null)}}>{data.datasets.map(d=><option key={d.id} value={d.id}>{d.name}</option>)}</select></label><label className="wide">锁定标尺<select aria-label="研究标尺" value={scaleId||data.scales[0]?.id||''} onChange={e=>setScaleId(e.target.value)}>{data.scales.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select></label><fieldset className="wide"><legend>选择评委 / 至少两名</legend><div className="rater-checks">{ds?.raters.map(r=><label key={r}><input type="checkbox" checked={raters.includes(r)} onChange={e=>setSelected(e.target.checked?[...raters,r]:raters.filter(x=>x!==r))}/>{r}</label>)}</div></fieldset><button disabled={task.busy||raters.length<2}>保存评委组合</button></form></section>}
  {canWrite&&<section className="paper"><h2>区间分析设置（随每次计算提交）</h2>
   <p className="caption">对共同完整任务整行有放回重抽样，重抽样内重算并列修正Kendall W与五级二次加权kappa；相同输入加相同设置可复现，设置与区间结果随运行保存并写入归档CSV。</p>
   <form className="grid-form interval-form" onSubmit={e=>{e.preventDefault()}}>
    <label>置信水平<select aria-label="置信水平" value={confidenceLevel} onChange={e=>setConfidenceLevel(+e.target.value)}>{[0.8,0.9,0.95,0.99].map(v=><option key={v} value={v}>{confidencePct(v)}</option>)}</select></label>
    <label>重抽样次数（100–10000）<input aria-label="重抽样次数" type="number" min={100} max={10000} step={100} value={resamples} onChange={e=>setResamples(+e.target.value)}/></label>
    <label>随机种子（0–2147483647）<input aria-label="随机种子" type="number" min={0} max={2147483647} step={1} value={seed} onChange={e=>setSeed(+e.target.value)}/></label>
   </form>
   {!intervalValid&&<Notice error>重抽样次数须在100–10000之间，随机种子须在0–2147483647之间。</Notice>}
  </section>}
  {task.error&&<Notice error>{task.error}</Notice>}
  <section className="paper"><h2>已锁定研究</h2>{data.studies.map(s=><article className="study-row" key={s.id}><div><span className="eyebrow">{s.rater_ids.length}名评委 / {s.rater_ids.join(' · ')}</span><h3>{s.name}</h3><p>{data.scales.find(l=>l.id===s.scale_id)?.name}</p></div>{canWrite&&<button className="secondary" disabled={task.busy||!intervalValid} title={intervalValid?'按上方区间设置计算':'区间设置不合法'} onClick={()=>task.execute(async()=>{await run({study_id:s.id,confidence_level:confidenceLevel,resamples,seed});await refresh();go('results')})}>计算一致性（{confidencePct(confidenceLevel)} / {resamples}次 / 种子{seed}）　→</button>}</article>)}</section>
  <section className="paper"><h2>后台计算队列</h2><div className="table-scroll"><table><thead><tr><th>研究</th><th>状态</th><th>区间设置</th><th>提交时间</th></tr></thead><tbody>{data.runs.map(r=><tr key={r.id}><td>{data.studies.find(s=>s.id===r.study_id)?.name}</td><td><Status value={r.status}/></td><td>{r.resamples==null?'历史运行 · 仅点估计':`${r.confidence_level!=null?confidencePct(r.confidence_level):''} / ${r.resamples}次 / 种子${r.seed}`}</td><td>{date(r.created_at)}</td></tr>)}</tbody></table></div></section>
 </>;
}
