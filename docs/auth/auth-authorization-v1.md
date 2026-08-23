# Auth + Authorization V1

Auth V1 adds a product security boundary around the frozen Legal RAG pipeline. It is multi-user, with `USER` and `ADMIN` roles, private document grants, and an independent Global corpus. It is not an organization/workspace model.

## Boundaries

- Browser identity is resolved once into `Principal { user_id, role, auth_session_id }`.
- Product routes require authentication. Debug and Evaluation additionally require `ADMIN` and their feature flag.
- `ADMIN` is not an implicit reader of another user's private content or chats.
- Explicit hidden resource identifiers return the same `404 RESOURCE_NOT_FOUND` as nonexistent identifiers.
- Workers are trusted internal callers; browser cookies are never propagated to them.

## Core RAG change audit

Blocks 1–3, Block 5, and Block 6 algorithms are unchanged. Dense Top50, Lexical Top50, lexical fallback, RRF k=60, base Top10, and Legal Hierarchy Retrieval V2 are unchanged. The only Block 4 amendment is an access predicate inside Dense and Lexical SQL before ranking. Block 6 remains `qwen3.5:9b` with `legal-rag-v2`.

## Provisioning

There is no public signup. Provision users with an authenticated admin endpoint or the interactive CLI:

```text
python -m app.auth.cli create-admin --email admin@example.com
python -m app.auth.cli create-user --email user@example.com
```

The CLI prompts for a temporary password unless `AUTH_BOOTSTRAP_PASSWORD` is supplied by a controlled deployment environment. No default password exists.

## Known limitations

V1 has no organizations, teams, arbitrary sharing, OIDC/SAML, MFA, password-reset email, PostgreSQL RLS, or custom roles. Broader adversarial hardening is a separate Security Hardening phase.
