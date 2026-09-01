# ARCHITECTURE_STATUS

**Project:** ZKD / Vietnamese Legal RAG
**Status:** Active architecture index
**Last updated:** 2026-09-01

This index changes no frozen document. It identifies which architecture material governs the active V1 product direction and prevents accidental execution of historical infrastructure plans.

## Active

| Document | Status | Meaning |
|---|---|---|
| `LOCAL_FIRST_COMPUTE_ARCHITECTURE_V1.md` | **ACTIVE V1 ARCHITECTURE CORRECTION** | The active product boundary: a lightweight online shell and user-owned compute/data by default. |

## Frozen historical/reference material

| Document | Status | Active-V1 interpretation |
|---|---|---|
| `HYBRID_RUNTIME_CONTRACT_V1.md` | **FROZEN REFERENCE** | Preserve compatible pairing, device lifecycle, capability, security, idempotency, and user-friendly-runtime concepts. Its cloud-canonical/generation-only placement is superseded for active V1 by the local-first correction. Do not edit it silently. |
| `HYBRID_RUNTIME_P1_CLOUD_PORTABILITY.md` | **HISTORICAL REFERENCE** | Portability evidence for the prior cloud-control-plane path; not an active-V1 provisioning plan. |
| `CLOUD_INFRASTRUCTURE_TOPOLOGY_V1.md` | **SUPERSEDED_FOR_ACTIVE_V1** | The always-on platform E5/retrieval/worker/object-storage topology must not be deployed for active V1. |
| `CLOUD_PROVIDER_SELECTION_V1.md` | **SUPERSEDED_FOR_ACTIVE_V1** | The DigitalOcean/SGP1 provider map is historical only. |
| `../deployment/STAGING_PROVISIONING_RUNBOOK_V1.md` | **SUPERSEDED_FOR_ACTIVE_V1** | Do not use it to provision staging without a later explicit human decision. |

## Terraform safety

`deployment/terraform/staging/` is historical, non-active infrastructure-as-code. It must not receive `terraform apply` for active V1. No DigitalOcean App Node, Worker Node, Managed PostgreSQL, Spaces bucket, Cloudflare staging resource, DNS change, or canonical-data migration is authorized by this status document.

The files remain available as reference for a possible future `PlatformCloudComputeProvider` tier, which would require a new approved product, data-ownership, and cost decision.
