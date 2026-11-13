const serviceLabels: Record<string, string> = {
  postgresql: "PostgreSQL",
  redis: "Redis",
};

export function serviceLabel(name: string): string {
  return serviceLabels[name] ?? name;
}

export function formatLatency(latencyMs: number | null): string {
  if (latencyMs === null) {
    return "—";
  }
  return `${latencyMs.toFixed(2)} ms`;
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}
