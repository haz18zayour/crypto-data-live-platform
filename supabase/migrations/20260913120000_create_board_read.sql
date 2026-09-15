create view public.board_read
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
  source_timestamp
from public.datapoints
order by indicator_key, asset, fetched_at desc, id desc;

revoke all on public.board_read from anon, authenticated;
grant select on public.board_read to anon, authenticated;
