"""Strict contracts for vendor responses."""

from pydantic import (
    BaseModel,
    ConfigDict,
    RootModel,
    StrictFloat,
    StrictInt,
    StrictStr,
    model_validator,
)

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


class CoinbaseCandle(BaseModel):
    """A Coinbase candle named in the venue's documented field order."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    time: StrictInt
    low: StrictFloat
    high: StrictFloat
    open: StrictFloat
    close: StrictFloat
    volume: StrictFloat

    @model_validator(mode="before")
    @classmethod
    def name_array_fields(cls, value: object) -> object:
        if not isinstance(value, (list, tuple)):
            return value

        fields = ("time", "low", "high", "open", "close", "volume")
        try:
            return dict(zip(fields, value, strict=True))
        except ValueError as error:
            raise ValueError(
                "Coinbase candles must contain exactly time, low, high, open, "
                "close, volume"
            ) from error


class CoinbaseCandleResponse(RootModel[tuple[CoinbaseCandle, ...]]):
    """The response contract for Coinbase's product-candles endpoint."""

    model_config = ConfigDict(frozen=True)
