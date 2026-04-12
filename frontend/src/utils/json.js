export function parseJsonInput(source, fallback = {}) {
  if (!source || !source.trim()) {
    return fallback;
  }
  return JSON.parse(source);
}

export function stringifyJson(value) {
  return JSON.stringify(value || {}, null, 2);
}
