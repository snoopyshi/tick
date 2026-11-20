from fastapi import APIRouter, HTTPException

from tick.market.catalog import CapabilityView, get_capability, list_capabilities
from tick.schemas.capabilities import (
    CapabilityListResponse,
    CapabilityOut,
    CoverageOut,
)

router = APIRouter(tags=["data"])


def _to_out(view: CapabilityView) -> CapabilityOut:
    coverage = None
    if view.coverage is not None:
        coverage = CoverageOut.model_validate(view.coverage, from_attributes=True)
    return CapabilityOut(
        id=view.id,
        title=view.title,
        status=view.status,
        grain=list(view.grain),
        columns=list(view.columns),
        adjust=view.adjust,
        depends_on=list(view.depends_on),
        producer=view.producer,
        path=view.path,
        coverage=coverage,
        issues=list(view.issues),
    )


@router.get("/data/capabilities", response_model=CapabilityListResponse)
async def get_capabilities() -> CapabilityListResponse:
    items = [_to_out(item) for item in list_capabilities()]
    return CapabilityListResponse(total=len(items), items=items)


@router.get("/data/capabilities/{capability_id}", response_model=CapabilityOut)
async def get_capability_by_id(capability_id: str) -> CapabilityOut:
    view = get_capability(capability_id)
    if view is None:
        raise HTTPException(status_code=404, detail="unknown capability")
    return _to_out(view)
