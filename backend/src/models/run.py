from sqlalchemy import String,Float,Integer,JSON,ForeignKey,Text
from sqlalchemy.orm import Mapped,mapped_column
from src.config.database import Base
class AgreementRun(Base):
 __tablename__="agreement_runs"
 id:Mapped[str]=mapped_column(String,primary_key=True)
 study_id:Mapped[str]=mapped_column(ForeignKey("agreement_studies.id"))
 status:Mapped[str]=mapped_column(String)
 result:Mapped[dict]=mapped_column(JSON,default=dict)
 error:Mapped[str]=mapped_column(Text,default="")
 # 区间分析设置；历史运行该三列为NULL，保持原有点估计结果
 confidence_level:Mapped[float|None]=mapped_column(Float,nullable=True)
 resamples:Mapped[int|None]=mapped_column(Integer,nullable=True)
 seed:Mapped[int|None]=mapped_column(Integer,nullable=True)
 created_at:Mapped[str]=mapped_column(String)
