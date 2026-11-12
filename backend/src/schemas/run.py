from pydantic import BaseModel,Field
class RunInput(BaseModel):
 study_id:str
 confidence_level:float=Field(default=0.95,ge=0.50,le=0.99)
 resamples:int=Field(default=1000,ge=100,le=10000)
 seed:int=Field(default=20261112,ge=0,le=2147483647)
