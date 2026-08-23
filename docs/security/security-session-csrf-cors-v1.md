# Session, CSRF, and CORS V1

Cookie authentication is protected by three cooperating controls: `SameSite=Lax`, exact trusted-origin validation for unsafe methods, and explicit CORS origins. Controlled cross-origin POST/DELETE mutations with a hostile `Origin` returned `403`, including login, logout, password change, account deletion, upload, retrieval, answer, and chat mutation paths.

Allowed preflight returned the exact configured origin and credential support. A hostile preflight returned `400` without `Access-Control-Allow-Origin`; wildcard credentialed CORS is not configured. Requests lacking browser Origin remain permitted for same-origin/non-browser clients, with authentication and authorization still required.

The raw session token remains only in the cookie and is never exposed to JavaScript. Local HTTP sets `Secure=false` only through the explicit local compose setting; the application default is secure.
