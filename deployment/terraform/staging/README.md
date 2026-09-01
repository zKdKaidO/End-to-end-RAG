# DigitalOcean staging Terraform declaration

This directory declares only the isolated `SGP1` staging control plane:

- `zkd-rag-staging-vpc`;
- App and Worker `s-4vcpu-8gb` Ubuntu 24.04 Droplets;
- a 1 vCPU / 2 GiB Managed PostgreSQL cluster attached to that VPC;
- a private, globally unique SGP1 Spaces bucket;
- Droplet firewalls that do not expose application ports and permit Redis only from the Worker tag.

It creates no central LLM, GPU, Qwen/Ollama runtime, LLM credit, billing resource, Cloudflare resource, production resource, or canonical-data migration.

## Prerequisites before any future apply

1. Human approval for billable staging creation.
2. DigitalOcean account/payment readiness and an exported `DIGITALOCEAN_TOKEN` with the minimum provisioning scope.
3. An existing/imported **public** SSH key ID or fingerprint; never put a private key in Terraform.
4. A collision-reviewed staging-only RFC1918 VPC CIDR.
5. A globally unique lowercase Spaces bucket name.
6. Terraform `>= 1.6.0` and the DigitalOcean provider download.

## Non-mutating validation

```text
terraform init -backend=false
terraform fmt -check
terraform validate
terraform plan -out=tfplan
```

`init`, `fmt`, `validate`, and `plan` do not create infrastructure. Do not run `apply` until a human has inspected the plan and explicitly approved the resulting billable resource set. `tfplan`, state, `.terraform`, secrets, and populated tfvars are ignored by Git.

## Apply boundary for a later phase

Only after the human approval above: create staging resources, retrieve private database/TLS details, create narrowly scoped Spaces credentials manually, configure the private App Node Redis endpoint, bootstrap the E5 artifact, create a **separate** Cloudflare staging tunnel and `staging.zkd.id.vn`, then run the acceptance checks in `../STAGING_PROVISIONING_RUNBOOK_V1.md`.

Never target `rag.zkd.id.vn`, the existing production tunnel, production state, or canonical development volumes from this Terraform state.
