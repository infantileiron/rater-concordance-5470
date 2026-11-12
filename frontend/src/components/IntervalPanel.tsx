import type {IntervalBlock,IntervalResult} from '../types/domain';
import {confidencePct,intervalText} from '../utils/format';
import {Notice} from './common/Notice';

function BlockLine({label,b}:{label:string;b:IntervalBlock}){
 return <tr><td>{label}</td><td>{intervalText(b)}</td><td>{b.estimable_resamples}</td><td>{b.not_estimable_resamples}</td><td className="interval-reason">{b.lower==null?b.reason:''}</td></tr>;
}

export function IntervalPanel({interval,pairs}:{interval:IntervalResult;pairs:{rater_a:string;rater_b:string}[]}){
 return <section className="paper interval-panel">
  <div className="section-heading"><h2>区间分析 · 整行重抽样</h2><span>{confidencePct(interval.confidence_level)}置信水平 / {interval.resamples}次重抽样 / 种子{interval.seed}</span></div>
  <p className="caption">{interval.method}。分位数口径：{interval.quantile_method}；重抽样池={interval.tasks_resampled}个共同完整任务，缺评分隔离任务不入池。相同输入与设置（置信水平/次数/种子）结果可复现。</p>
  <div className="table-scroll"><table>
   <thead><tr><th>指标</th><th>{confidencePct(interval.confidence_level)}置信区间</th><th>可估计重抽样</th><th>不可估计重抽样</th><th>不可估计/样本不足原因</th></tr></thead>
   <tbody>
    <BlockLine label="并列校正 Kendall W" b={interval.kendall}/>
    <BlockLine label="成对κ均值（可估计对的描述均值）" b={interval.mean_pair_kappa}/>
    {interval.pairs.map((b,i)=><BlockLine key={i} label={`加权κ · ${pairs[i]?.rater_a} × ${pairs[i]?.rater_b}`} b={b}/>)}
   </tbody>
  </table></div>
  <Notice>不可估计的重抽样（秩无变异、期望分歧为0、完整任务不足等）单独计数，不计入区间样本；可估计样本少于2个时不给出上下界并在末列说明原因，不以0或点估计替代。</Notice>
  <ul className="interval-notes">{interval.note.map((s,i)=><li key={i}>{s}</li>)}</ul>
  <p className="caption">区间依据校验码 {interval.checksum?interval.checksum.slice(0,24):'不可用'}（完整校验码见归档CSV的interval_checksum列），与点估计输入校验码共同构成复现依据。</p>
 </section>;
}
