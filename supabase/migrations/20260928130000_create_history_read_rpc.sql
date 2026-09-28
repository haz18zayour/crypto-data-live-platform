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
      and source_vendor = p_source_vendor
      and origin in ('live', 'backfill')
      and status in ('OK', 'STALE')
      and source_timestamp is not null
    order by source_timestamp desc, id desc
    limit greatest(coalesce(p_point_limit, 0), 0)
  ) as history_row;
$$;

revoke all on function public.history_read(text, text, text, integer) from public;
grant execute on function public.history_read(text, text, text, integer) to anon, authenticated;
