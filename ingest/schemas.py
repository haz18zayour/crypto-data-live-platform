"""Strict contracts for vendor responses."""

from pydantic import BaseModel, ConfigDict, StrictStr

type OkxCandle = tuple[
    StrictStr,
    StrictStr,
    StrictStr,
    StrictStr,
    StrictStr,
    StrictStr,
    StrictStr,
    StrictStr,
    StrictStr,
]


class OkxCandleResponse(BaseModel):
    """The response contract for OKX's market-candles endpoint."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: StrictStr
    msg: StrictStr
    data: tuple[OkxCandle, ...]
