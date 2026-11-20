"""数据能力查询接口的响应模型。

这个文件不判断能力是否可用。声明、清单和 ``ready`` / ``invalid`` / ``missing``
在 ``tick.market.catalog`` 里算好，接口层把 ``CapabilityView`` 转成这里的模型再返回。
"""

from pydantic import BaseModel, Field


class CoverageOut(BaseModel):
    """一份清单里的覆盖信息。清单不存在或读不出来时，外层 ``coverage`` 为 null。

    日期、``asset_types`` 和五个事件计数只在对应能力的清单里出现，其余为 null。
    """

    rows: int
    bytes: int
    symbols: int
    vendor: str
    snapshot_id: str
    produced_at: str
    min_date: str | None = None
    max_date: str | None = None
    asset_types: dict[str, int] | None = None
    events_applied: int | None = None
    events_before_window: int | None = None
    events_after_window: int | None = None
    events_zero: int | None = None
    events_no_bars: int | None = None


class CapabilityOut(BaseModel):
    """一条数据能力。``GET /api/v1/data/capabilities/{id}`` 直接返回它。

    ``status`` 取 ``ready``、``invalid``、``missing``。``issues`` 是固定代码；
    ``ready`` 时为空数组。``path`` 是相对 ``DATA_DIR`` 的路径，不是本机绝对路径。
    """

    id: str
    title: str
    status: str
    grain: list[str]
    columns: list[str]
    adjust: str | None = None
    depends_on: list[str]
    producer: str
    path: str
    coverage: CoverageOut | None = None
    issues: list[str]


class CapabilityListResponse(BaseModel):
    """``GET /api/v1/data/capabilities`` 的列表。``items`` 的顺序与代码里的声明一致。"""

    total: int = Field(ge=0)
    items: list[CapabilityOut]
