from pydantic import BaseModel


class DemandCapBody(BaseModel):
    # 不用 Field(ge=...) 约束：业务校验在引擎内完成，以便返回可读错误码与字段名。
    demand_kw: float
    cap_kw: float
    convert_coef: float


class DemandCapProbe(BaseModel):
    """只读探针：可用已入库参数（account_id + period），也可现场传参试算。"""

    account_id: int | None = None
    period: str | None = None
    # 试算用基础电量与尖峰，仅用于预览合并后的金额，不落库。
    kwh: float | None = None
    peak: bool = False
    demand_kw: float | None = None
    cap_kw: float | None = None
    convert_coef: float | None = None


class DemandCapOut(BaseModel):
    account_id: int
    period: str
    demand_kw: float
    cap_kw: float
    convert_coef: float
    updated_at: str
