alter table public.datapoints
  add column reference_period text,
  add column published_at timestamptz;

create or replace view public.datapoints_read
with (security_invoker = true)
as
select
  id,
  indicator_key,
  asset,
  measured_on,
  value,
  status,
  reason,
  source_vendor,
  endpoint,
  source_field,
  fetched_at,
  source_timestamp,
  reference_period,
  published_at
from public.datapoints;

revoke all on public.datapoints_read from anon, authenticated;
grant select on public.datapoints_read to anon, authenticated;

create or replace view public.board_read
with (security_invoker = true)
as
select distinct on (indicator_key, asset)
  id,
  indicator_key,
  asset,
  measured_on,
  value,
  status,
  reason,
  source_vendor,
  endpoint,
  source_field,
  fetched_at,
  source_timestamp,
  reference_period,
  published_at
from public.datapoints
order by indicator_key, asset, fetched_at desc, id desc;

revoke all on public.board_read from anon, authenticated;
grant select on public.board_read to anon, authenticated;
