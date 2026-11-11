export function number(value: number | null | undefined): string {
  return value == null
    ? "Unknown"
    : new Intl.NumberFormat("en", { maximumFractionDigits: 1 }).format(value);
}
export function duration(ms: number | null | undefined): string {
  return ms == null
    ? "Unknown"
    : ms < 1000
      ? `${Math.round(ms)} ms`
      : ms < 60000
        ? `${(ms / 1000).toFixed(1)} s`
        : `${(ms / 60000).toFixed(1)} min`;
}
export function rate(value: number | null | undefined): string {
  return value == null ? "—" : `${Math.round(value * 100)}%`;
}
export function date(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf())
    ? value
    : new Intl.DateTimeFormat("en", {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
      }).format(parsed);
}
export function day(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf())
    ? value
    : new Intl.DateTimeFormat("en", {
        month: "short",
        day: "numeric",
        year: "numeric",
      }).format(parsed);
}
export function human(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}
export function active(state: string): boolean {
  return ["queued", "running"].includes(state);
}
export function money(value: number | null, provenance?: string): string {
  return provenance === "not_applicable"
    ? "No API fees"
    : value == null
      ? "Unknown"
      : `$${value.toFixed(value === 0 ? 2 : 4)}`;
}
