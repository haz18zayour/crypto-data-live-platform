alter table public.datapoints
  add column origin text not null default 'live';

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
  published_at,
  origin
from public.datapoints
where origin = 'live';

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
  published_at,
  origin
from public.datapoints
where origin = 'live'
order by indicator_key, asset, fetched_at desc, id desc;

revoke all on public.board_read from anon, authenticated;
grant select on public.board_read to anon, authenticated;
