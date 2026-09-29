export function formatUtcTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  const months = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];
  const day = String(date.getUTCDate()).padStart(2, "0");
  const time = [date.getUTCHours(), date.getUTCMinutes(), date.getUTCSeconds()]
    .map((part) => String(part).padStart(2, "0"))
    .join(":");
  return `${day} ${months[date.getUTCMonth()]} ${date.getUTCFullYear()}, ${time} UTC`;
}

export function formatUtcDate(timestamp: string): string {
  return formatUtcTimestamp(timestamp).split(",")[0];
}

export function FrozenBadge({
  sinceSourceTimestamp,
}: {
  sinceSourceTimestamp: string;
}) {
  return (
    <span className="frozen-badge">
      unchanged since{" "}
      <time dateTime={sinceSourceTimestamp}>
        {formatUtcDate(sinceSourceTimestamp)}
      </time>
    </span>
  );
}
