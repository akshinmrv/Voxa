// Base URL of the local `voxa serve` backend. Override with NEXT_PUBLIC_VOXA_API.
export const API_BASE = (
  process.env.NEXT_PUBLIC_VOXA_API ?? "http://localhost:8000"
).replace(/\/$/, "");
