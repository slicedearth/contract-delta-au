export const formatMoney = (value: string | null, currency = "AUD") => {
  if (value === null) return "Not reported";
  return new Intl.NumberFormat("en-AU", {
    style: "currency",
    currency,
    maximumFractionDigits: 2
  }).format(Number(value));
};

export const formatDate = (value: string | null, withTime = false) => {
  if (!value) return "Not reported";
  const options: Intl.DateTimeFormatOptions = withTime
    ? {
        day: "numeric",
        month: "long",
        year: "numeric",
        hour: "numeric",
        minute: "2-digit",
        timeZone: "Australia/Sydney",
        timeZoneName: "short"
      }
    : { dateStyle: "medium", timeZone: "Australia/Sydney" };
  const parsed = value.length === 10 ? new Date(`${value}T00:00:00+10:00`) : new Date(value);
  return new Intl.DateTimeFormat("en-AU", options).format(parsed);
};

export const formatValue = (value: string | null, field: string, currency = "AUD") => {
  if (value === null) return "Not reported";
  if (field === "reported_value") return formatMoney(value, currency);
  if (field.includes("date")) return formatDate(value);
  return value;
};

export const truncateHash = (value: string) => `${value.slice(0, 12)}…${value.slice(-8)}`;
