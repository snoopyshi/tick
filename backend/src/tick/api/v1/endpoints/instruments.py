from fastapi import APIRouter, HTTPException, Query

from tick.market.instruments_cache import list_instruments
from tick.market.schema import ASSET_TYPES
from tick.schemas.instruments import InstrumentListResponse, InstrumentOut

router = APIRouter(tags=["instruments"])

_MAX_LIMIT = 500


@router.get("/instruments", response_model=InstrumentListResponse)
async def get_instruments(
    q: str | None = Query(default=None, description="Match symbol / ticker / name"),
    asset_type: str | None = Query(
        default=None,
        description="Comma-separated asset types; omit for all",
    ),
    limit: int = Query(default=50, ge=1, le=_MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> InstrumentListResponse:
    asset_types: list[str] | None = None
    if asset_type is not None and asset_type.strip():
        asset_types = [part.strip() for part in asset_type.split(",") if part.strip()]
        unknown = sorted({part for part in asset_types if part not in ASSET_TYPES})
        if unknown:
            raise HTTPException(
                status_code=422,
                detail=f"unknown asset_type(s): {unknown}",
            )

    try:
        items, total = list_instruments(
            q=q,
            asset_types=asset_types,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return InstrumentListResponse(
        total=total,
        items=[
            InstrumentOut.model_validate(item, from_attributes=True)
            for item in items
        ],
    )
