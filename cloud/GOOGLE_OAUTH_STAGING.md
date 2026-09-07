# Google OpenID Connect — staging setup

Create a Google Cloud OAuth client of type **Web application**. Configure only:

- Authorized JavaScript origin: `https://zkd-control-plane-staging.zkd-rag.workers.dev`
- Authorized redirect URI: `https://zkd-control-plane-staging.zkd-rag.workers.dev/api/v1/auth/google/callback`
- Scopes: `openid`, `email`, `profile`

Install the values only as staging Worker secrets:

```powershell
cd A:\RAG\cloud
npx wrangler secret put GOOGLE_CLIENT_ID --env staging
npx wrangler secret put GOOGLE_CLIENT_SECRET --env staging
```

Never put either value in `wrangler.jsonc`, D1, source control, frontend build
variables, or logs. Production must later use its separate callback
`https://rag.zkd.id.vn/api/v1/auth/google/callback` and separate secrets; it is
not configured by this staging change.
