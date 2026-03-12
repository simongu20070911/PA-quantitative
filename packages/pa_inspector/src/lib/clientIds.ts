function hex(bytes: Uint8Array) {
  return Array.from(bytes, (value) => value.toString(16).padStart(2, "0")).join("");
}

export function createClientUuid(): string {
  const cryptoApi = globalThis.crypto;
  if (cryptoApi && typeof cryptoApi.randomUUID === "function") {
    return cryptoApi.randomUUID();
  }

  if (cryptoApi && typeof cryptoApi.getRandomValues === "function") {
    const bytes = new Uint8Array(16);
    cryptoApi.getRandomValues(bytes);
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    return [
      hex(bytes.slice(0, 4)),
      hex(bytes.slice(4, 6)),
      hex(bytes.slice(6, 8)),
      hex(bytes.slice(8, 10)),
      hex(bytes.slice(10, 16)),
    ].join("-");
  }

  const timestamp = Date.now().toString(16).padStart(12, "0").slice(-12);
  const random = Math.random().toString(16).slice(2, 14).padEnd(12, "0");
  return `fallback-${timestamp}-${random}`;
}
