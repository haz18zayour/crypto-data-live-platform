create or replace function public.integrity_read(p_registry jsonb)
returns jsonb
language sql
stable
as $$
  with computed as (
    select statement_timestamp() as computed_at
  ),
  registry as (
    select
      key,
      vendor,
      freshness_warn_seconds,
      freshness_stale_seconds,
      frozen_after_observations,
      expected_constant,
      derives_from,
      frozen_propagation_unavailable,
      freshness_unmeasurable
    from jsonb_to_recordset(coalesce(p_registry, '[]'::jsonb)) as entry(
      key text,
      vendor text,
      freshness_warn_seconds integer,
      freshness_stale_seconds integer,
      frozen_after_observations integer,
      expected_constant text,
      derives_from text,
      frozen_propagation_unavailable text,
      freshness_unmeasurable text
    )
  ),
  cells as (
    select
      d.indicator_key,
      d.asset,
      d.source_vendor,
      max(d.source_timestamp) as latest_source_timestamp
    from public.datapoints d
      join registry r on r.key = d.indicator_key and r.vendor = d.source_vendor
    where d.origin in ('live', 'backfill')
    group by d.indicator_key, d.asset, d.source_vendor
  ),
  observations as (
    select
      distinct_observation.indicator_key,
      distinct_observation.asset,
      distinct_observation.source_vendor,
      distinct_observation.source_timestamp,
      distinct_observation.value,
      row_number() over (
        partition by
          distinct_observation.indicator_key,
          distinct_observation.asset,
          distinct_observation.source_vendor
        order by distinct_observation.source_timestamp desc
      ) as observation_rank
    from (
      select distinct on (
        d.indicator_key,
        d.asset,
        d.source_vendor,
        d.source_timestamp
      )
        d.indicator_key,
        d.asset,
        d.source_vendor,
        d.source_timestamp,
        d.value
      from public.datapoints d
        join registry r on r.key = d.indicator_key and r.vendor = d.source_vendor
      where d.origin in ('live', 'backfill')
        and d.status = 'OK'
        and d.value is not null
        and d.source_timestamp is not null
      order by
        d.indicator_key,
        d.asset,
        d.source_vendor,
        d.source_timestamp,
        d.fetched_at desc,
        d.id desc
    ) distinct_observation
  ),
  direct_frozen as (
    select
      c.indicator_key,
      c.asset,
      c.source_vendor,
      case
        when r.expected_constant is not null then false
        when r.frozen_propagation_unavailable is not null then null::boolean
        when count(o.value) = r.frozen_after_observations
          and min(o.value) = max(o.value)
          then true
        else false
      end as frozen,
      case
        when r.expected_constant is not null then 'expected_constant'
        when r.frozen_propagation_unavailable is not null then 'propagation_unavailable'
        when count(o.value) = r.frozen_after_observations
          and min(o.value) = max(o.value)
          then 'frozen'
        else 'not_frozen'
      end as frozen_state,
      case
        when r.expected_constant is null
          and r.frozen_propagation_unavailable is null
          and count(o.value) = r.frozen_after_observations
          and min(o.value) = max(o.value)
          then min(o.source_timestamp)
        else null::timestamptz
      end as frozen_since_source_timestamp
    from cells c
      join registry r on r.key = c.indicator_key and r.vendor = c.source_vendor
      left join observations o
        on o.indicator_key = c.indicator_key
        and o.asset = c.asset
        and o.source_vendor = c.source_vendor
        and o.observation_rank <= r.frozen_after_observations
    group by
      c.indicator_key,
      c.asset,
      c.source_vendor,
      r.frozen_after_observations,
      r.expected_constant,
      r.frozen_propagation_unavailable
  ),
  resolved as (
    select
      c.indicator_key,
      c.asset,
      c.source_vendor,
      c.latest_source_timestamp,
      r.freshness_warn_seconds,
      r.freshness_stale_seconds,
      r.freshness_unmeasurable,
      r.frozen_after_observations,
      r.expected_constant,
      r.derives_from,
      r.frozen_propagation_unavailable,
      case
        when r.frozen_propagation_unavailable is not null then null::boolean
        when r.derives_from is not null then root.frozen
        else direct.frozen
      end as frozen,
      case
        when r.frozen_propagation_unavailable is not null then 'propagation_unavailable'
        when r.derives_from is not null then coalesce(root.frozen_state, 'root_unavailable')
        else direct.frozen_state
      end as frozen_state,
      case
        when r.frozen_propagation_unavailable is not null then null::timestamptz
        when r.derives_from is not null then root.frozen_since_source_timestamp
        else direct.frozen_since_source_timestamp
      end as frozen_since_source_timestamp
    from cells c
      join registry r on r.key = c.indicator_key and r.vendor = c.source_vendor
      left join direct_frozen direct
        on direct.indicator_key = c.indicator_key
        and direct.asset = c.asset
        and direct.source_vendor = c.source_vendor
      left join registry root_registry
        on root_registry.key = r.derives_from
      left join direct_frozen root
        on root.indicator_key = r.derives_from
        and root.asset = c.asset
        and root.source_vendor = root_registry.vendor
  ),
  rows as (
    select
      jsonb_build_object(
        'indicator_key', r.indicator_key,
        'asset', r.asset,
        'source_vendor', r.source_vendor,
        'computed_at', c.computed_at,
        'latest_source_timestamp', r.latest_source_timestamp,
        'source_timestamp_age_seconds',
          case
            when r.latest_source_timestamp is null then null
            else extract(epoch from c.computed_at - r.latest_source_timestamp)::integer
          end,
        'freshness_state',
          case
            when r.freshness_unmeasurable is not null then 'unmeasurable'
            when r.latest_source_timestamp is null then 'stale'
            when extract(epoch from c.computed_at - r.latest_source_timestamp)
              >= r.freshness_stale_seconds then 'stale'
            when extract(epoch from c.computed_at - r.latest_source_timestamp)
              >= r.freshness_warn_seconds then 'warn'
            else 'fresh'
          end,
        'freshness_warn_seconds', r.freshness_warn_seconds,
        'freshness_stale_seconds', r.freshness_stale_seconds,
        'freshness_unmeasurable_reason', r.freshness_unmeasurable,
        'frozen', r.frozen,
        'frozen_state', r.frozen_state,
        'frozen_since_source_timestamp', r.frozen_since_source_timestamp,
        'frozen_after_observations', r.frozen_after_observations,
        'expected_constant_reason', r.expected_constant,
        'derives_from', r.derives_from,
        'frozen_propagation_unavailable_reason', r.frozen_propagation_unavailable
      ) as payload
    from resolved r
      cross join computed c
  )
  select coalesce(
    jsonb_agg(payload order by payload->>'indicator_key', payload->>'asset', payload->>'source_vendor'),
    '[]'::jsonb
  )
  from rows;
$$;

revoke all on function public.integrity_read(jsonb) from public;
grant execute on function public.integrity_read(jsonb) to anon, authenticated;

notify pgrst, 'reload schema';
