"""Strict contracts for vendor responses."""

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
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


class OkxFundingRateHistoryEntry(BaseModel):
    """One settled row from OKX's funding-rate-history endpoint."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    formula_type: StrictStr = Field(alias="formulaType")
    funding_rate: StrictStr = Field(alias="fundingRate")
    funding_time: StrictStr = Field(alias="fundingTime")
    inst_id: StrictStr = Field(alias="instId")
    inst_type: StrictStr = Field(alias="instType")
    method: StrictStr
    realized_rate: StrictStr = Field(alias="realizedRate")


class OkxFundingRateHistoryResponse(BaseModel):
    """The response contract for OKX's settled funding-rate endpoint."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: StrictStr
    msg: StrictStr
    data: tuple[OkxFundingRateHistoryEntry, ...]


class OkxOpenInterestEntry(BaseModel):
    """One row from OKX's public open-interest endpoint."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    inst_id: StrictStr = Field(alias="instId")
    inst_type: StrictStr = Field(alias="instType")
    oi: StrictStr
    oi_ccy: StrictStr = Field(alias="oiCcy")
    oi_usd: StrictStr = Field(alias="oiUsd")
    ts: StrictStr


class OkxOpenInterestResponse(BaseModel):
    """The response contract for OKX's public open-interest endpoint."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: StrictStr
    msg: StrictStr
    data: tuple[OkxOpenInterestEntry, ...]


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
