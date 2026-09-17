from pydantic import BaseModel, Field


class BillRequest(BaseModel):
    account_id: int | None = None
    kwh: float = Field(ge=0)
    peak: bool = False
    persist: bool = True
    # 账期缺省取当前月；当 account_id 在该账期已存封顶参数时自动并入附加电量。
    period: str | None = None
    # 也允许随单临时传入封顶参数（不落户参数），三者需同时给出。
    demand_kw: float | None = None
    cap_kw: float | None = None
    convert_coef: float | None = None


class CompareRequest(BaseModel):
    kwh: float = Field(ge=0)
    persist: bool = False


class CalcRunOut(BaseModel):
    id: int
    kind: str
    account_id: int | None
    input_json: str
    result_json: str
    created_at: str
