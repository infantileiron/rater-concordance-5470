-- 002: 区间分析（bootstrap）设置列。
-- 初次部署由SQLAlchemy元数据直接建出该三列；已部署的历史库执行本ALTER，
-- 历史运行三列为NULL，worker与结果页按原有点估计口径处理，旧归档CSV结构不变。
ALTER TABLE agreement_runs ADD COLUMN IF NOT EXISTS confidence_level DOUBLE PRECISION;
ALTER TABLE agreement_runs ADD COLUMN resamples INTEGER;
ALTER TABLE agreement_runs ADD COLUMN seed INTEGER;
