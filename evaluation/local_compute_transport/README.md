# ZKD Compute transport probe

This directory is an isolated, non-production acceptance probe for the selected
Browser-to-Compute topology:

```text
product-like HTTPS Origin -> http://127.0.0.1:<ephemeral-port>
```

The executable probe lives in `app.local_compute` and is exercised by
`tests/unit/local_compute/test_runtime.py`. It starts a literal-loopback
ephemeral HTTP listener, sends synthetic bytes directly through it, and checks
the exact CORS/PNA preflight, authenticated request, and foreign-origin denial
path. It contains no frontend code, real documents, model loading, platform
relay, or production route registration.

The HTTP-level probe passed. It is deliberately not recorded as browser
acceptance: a supported Chrome/Edge automation surface was unavailable in this
host. Before release, run the same synthetic probe from a product-equivalent
HTTPS test origin in Chrome and Edge without security flags.
