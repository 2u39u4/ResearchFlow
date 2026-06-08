export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("athena_token");
}

export function setStoredToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) localStorage.setItem("athena_token", token);
  else localStorage.removeItem("athena_token");
}
