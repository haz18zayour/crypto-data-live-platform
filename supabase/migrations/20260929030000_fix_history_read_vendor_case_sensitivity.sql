-- Confirmed live, 2026-09-29: web/src/data.ts uppercases source_vendor for display
-- (row.source_vendor.toUpperCase()) and CellDetail.tsx passes that same display value
-- straight through to history_read's p_source_vendor parameter. The stored column is
-- lowercase (e.g. 'okx'), so the original exact-match comparison always returned zero
-- rows for every cell on the live board - the RPC worked correctly in isolation (proven
-- by US-902's own tests, which pass source_vendor exactly as stored) but never once
-- returned real data through the actual browser call path. Comparing case-insensitively
-- is the correct, permanent fix: source_vendor is an internal identifier, not something
-- this project treats two different cases of as two different vendors.
create or replace function public.history_read(
  p_indicator_key text,
  p_asset text,
  p_source_vendor text,
  p_point_limit integer
)
returns jsonb
language sql
stable
as $$
  select coalesce(jsonb_agg(to_jsonb(history_row) order by history_row.source_timestamp desc, history_row.id desc), '[]'::jsonb)
  from (
    select
      id,
      indicator_key,
      asset,
      measured_on,
      value,
      status,
      source_vendor,
      endpoint,
      source_field,
      fetched_at,
      source_timestamp,
      reference_period,
      published_at,
      origin
    from public.datapoints
    where indicator_key = p_indicator_key
      and asset = p_asset
      and lower(source_vendor) = lower(p_source_vendor)
      and origin in ('live', 'backfill')
      and status in ('OK', 'STALE')
      and source_timestamp is not null
    order by source_timestamp desc, id desc
    limit greatest(coalesce(p_point_limit, 0), 0)
  ) as history_row;
$$;

revoke all on function public.history_read(text, text, text, integer) from public;
grant execute on function public.history_read(text, text, text, integer) to anon, authenticated;
