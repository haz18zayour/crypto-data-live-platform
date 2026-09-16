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


type OkxLongShortRatioEntry = tuple[StrictStr, StrictStr]


class OkxLongShortRatioResponse(BaseModel):
    """The response contract for OKX's long/short account-ratio endpoint."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: StrictStr
    msg: StrictStr
    data: tuple[OkxLongShortRatioEntry, ...]


type OkxTakerVolumeEntry = tuple[StrictStr, StrictStr, StrictStr]


class OkxTakerVolumeResponse(BaseModel):
    """The response contract for OKX's taker buy/sell volume endpoint."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: StrictStr
    msg: StrictStr
    data: tuple[OkxTakerVolumeEntry, ...]


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


class CoinMetricsAssetMetricsEntry(BaseModel):
    """One row from Coin Metrics' asset-metrics endpoint."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    asset: StrictStr
    time: StrictStr
    CapMVRVCur: StrictStr | None = None
    AdrActCnt: StrictStr | None = None
    FlowInExNtv: StrictStr | None = None
    FlowOutExNtv: StrictStr | None = None


class CoinMetricsAssetMetricsResponse(BaseModel):
    """The response contract for Coin Metrics' asset-metrics endpoint."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    data: tuple[CoinMetricsAssetMetricsEntry, ...]


class SolanaAccountKey(BaseModel):
    """One account key from a jsonParsed Solana transaction message."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pubkey: StrictStr
    signer: bool
    source: StrictStr | None = None
    writable: bool


class SolanaInstruction(BaseModel):
    """One top-level Solana instruction, parsed or partially decoded."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    accounts: tuple[StrictStr, ...] | None = None
    data: StrictStr | None = None
    parsed: object | None = None
    program: StrictStr | None = None
    program_id: StrictStr = Field(alias="programId")
    stack_height: StrictInt | None = Field(default=None, alias="stackHeight")


class SolanaMessage(BaseModel):
    """The transaction message fields needed to classify and count activity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    account_keys: tuple[SolanaAccountKey, ...] = Field(alias="accountKeys")
    instructions: tuple[SolanaInstruction, ...]
    recent_blockhash: StrictStr = Field(alias="recentBlockhash")
    # Present on every real v0 transaction (confirmed live against Helius, 2026-09-16), empty
    # for legacy ones. Not consumed by vote classification or signer counting, but extra="forbid"
    # rejects the field entirely if it is not declared, so a real response fails to parse.
    address_table_lookups: tuple[object, ...] = Field(
        default=(), alias="addressTableLookups"
    )


class SolanaTransactionPayload(BaseModel):
    """The parsed transaction payload inside a block transaction row."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    message: SolanaMessage
    signatures: tuple[StrictStr, ...]


class SolanaBlockTransaction(BaseModel):
    """One transaction row from getBlock(transactionDetails=full)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    meta: object | None
    transaction: SolanaTransactionPayload
    version: StrictStr | StrictInt | None = None


class SolanaBlock(BaseModel):
    """The getBlock result fields this fetcher consumes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    block_height: StrictInt | None = Field(default=None, alias="blockHeight")
    block_time: StrictInt | None = Field(alias="blockTime")
    blockhash: StrictStr
    parent_slot: StrictInt = Field(alias="parentSlot")
    previous_blockhash: StrictStr = Field(alias="previousBlockhash")
    transactions: tuple[SolanaBlockTransaction, ...]


class SolanaGetBlockResponse(BaseModel):
    """The JSON-RPC success shape for a Solana getBlock call."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    jsonrpc: StrictStr
    result: SolanaBlock | None
    id: StrictInt | StrictStr
