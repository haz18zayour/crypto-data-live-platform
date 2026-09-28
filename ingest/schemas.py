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

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    asset: StrictStr
    time: StrictStr
    CapMVRVCur: StrictStr | None = None
    AdrActCnt: StrictStr | None = None
    FlowInExNtv: StrictStr | None = None
    FlowOutExNtv: StrictStr | None = None
    # Present whenever a metric's value is still preliminary (confirmed live, 2026-09-16:
    # "flash" on real exchange-flow data) — Coin Metrics revises flash values as more data
    # arrives. Not yet acted on by the fetcher (accepted so extra="forbid" doesn't reject a
    # real response), but this is a genuine data-quality signal worth disclosing later, not
    # a field to silently discard.
    flow_in_status: StrictStr | None = Field(default=None, alias="FlowInExNtv-status")
    flow_in_status_time: StrictStr | None = Field(
        default=None, alias="FlowInExNtv-status-time"
    )
    flow_out_status: StrictStr | None = Field(default=None, alias="FlowOutExNtv-status")
    flow_out_status_time: StrictStr | None = Field(
        default=None, alias="FlowOutExNtv-status-time"
    )


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


class SolanaTransactionConfig(BaseModel):
    """Present only on version-1 transactions (confirmed live against Helius, 2026-09-16)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    priority_fee: StrictInt | None = Field(default=None, alias="priorityFee")
    compute_unit_limit: StrictInt | None = Field(default=None, alias="computeUnitLimit")
    loaded_accounts_data_size_limit: StrictInt | None = Field(
        default=None, alias="loadedAccountsDataSizeLimit"
    )
    heap_size: StrictInt | None = Field(default=None, alias="heapSize")


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
    # Present only on version-1 transactions (confirmed live, 2026-09-16), absent on legacy
    # and v0 ones. Not consumed by vote classification or signer counting, but extra="forbid"
    # rejects the field entirely if it is not declared.
    transaction_config: SolanaTransactionConfig | None = Field(
        default=None, alias="transactionConfig"
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


class ValidatorsAppValidator(BaseModel):
    """One validator row from Validators.app's Solana validators endpoint.

    Confirmed live (2026-09-16): the epochs endpoint's total_active_stake/total_rewards are
    permanently null (checked across a month of epochs, not just the in-progress one), so this
    project sums active_stake across every validator here instead. Fields this project does not
    consume are typed loosely (object) rather than pinned exactly, since their precise shape
    across all ~700 live validators was not exhaustively verified and pinning them risks the
    same brittleness this project has hit before on fields nobody reads.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    network: StrictStr
    account: StrictStr
    active_stake: StrictInt | None
    name: object = None
    keybase_id: object = None
    www_url: object = None
    details: object = None
    avatar_url: object = None
    created_at: object = None
    updated_at: object = None
    admin_warning: object = None
    jito: object = None
    jito_commission: object = None
    stake_pools_list: object = None
    is_active: object = None
    is_dz: object = None
    avatar_file_url: object = None
    authorized_withdrawer_score: object = None
    commission: object = None
    data_center_concentration_score: object = None
    delinquent: object = None
    published_information_score: object = None
    root_distance_score: object = None
    security_report_score: object = None
    skipped_slot_score: object = None
    skipped_after_score: object = None
    software_version: object = None
    software_version_score: object = None
    stake_concentration_score: object = None
    consensus_mods_score: object = None
    vote_latency_score: object = None
    total_score: object = None
    vote_distance_score: object = None
    software_client: object = None
    software_client_id: object = None
    ip: object = None
    data_center_key: object = None
    autonomous_system_number: object = None
    latitude: object = None
    longitude: object = None
    data_center_host: object = None
    vote_account: object = None
    epoch_credits: object = None
    epoch: object = None
    skipped_slots: object = None
    skipped_slot_percent: object = None
    ping_time: object = None
    url: object = None


class ValidatorsAppValidatorsResponse(RootModel[tuple[ValidatorsAppValidator, ...]]):
    """The response contract for Validators.app's validators-list endpoint."""

    model_config = ConfigDict(frozen=True)


class FredObservation(BaseModel):
    """One observation row from FRED's series/observations endpoint."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    realtime_start: StrictStr
    realtime_end: StrictStr
    date: StrictStr
    value: StrictStr


class FredSeriesObservationsResponse(BaseModel):
    """The response contract for FRED's series/observations endpoint."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    realtime_start: StrictStr
    realtime_end: StrictStr
    observation_start: StrictStr
    observation_end: StrictStr
    units: StrictStr
    output_type: StrictInt
    file_type: StrictStr
    order_by: StrictStr
    sort_order: StrictStr
    count: StrictInt
    offset: StrictInt
    limit: StrictInt
    observations: tuple[FredObservation, ...]


class SosoValueEtfSummaryHistoryEntry(BaseModel):
    """One aggregate row from SoSoValue's ETF summary-history endpoint.

    Confirmed live, 2026-09-28: money fields arrive as JSON floats, not the long-decimal
    strings the original research (and docs examples) described — StrictFloat here, parsed
    via Decimal(str(value)) in the fetcher to avoid float-to-Decimal binary imprecision.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    date: StrictStr
    total_net_inflow: StrictFloat
    total_value_traded: StrictFloat
    total_net_assets: StrictFloat
    cum_net_inflow: StrictFloat


class SosoValueEtfSummaryHistoryResponse(BaseModel):
    """The response contract for SoSoValue's ETF summary-history endpoint."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: StrictInt
    message: StrictStr
    data: tuple[SosoValueEtfSummaryHistoryEntry, ...]
    # Present on every real response (confirmed live, 2026-09-28), always null so far, but
    # extra="forbid" rejects it if undeclared.
    details: object | None = None


class DefiLlamaPeggedAmounts(BaseModel):
    """Stablecoin totals grouped by the fiat/asset peg tracked by DefiLlama."""

    model_config = ConfigDict(extra="allow", frozen=True)

    pegged_usd: StrictFloat | StrictInt = Field(alias="peggedUSD")


class DefiLlamaStablecoinChain(BaseModel):
    """One current stablecoin-supply total from DefiLlama's chain list."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    gecko_id: StrictStr | None
    total_circulating_usd: DefiLlamaPeggedAmounts = Field(
        alias="totalCirculatingUSD"
    )
    token_symbol: StrictStr | None = Field(alias="tokenSymbol")
    name: StrictStr


class DefiLlamaStablecoinChainsResponse(
    RootModel[tuple[DefiLlamaStablecoinChain, ...]]
):
    """The response contract for DefiLlama's stablecoinchains endpoint."""

    model_config = ConfigDict(frozen=True)
