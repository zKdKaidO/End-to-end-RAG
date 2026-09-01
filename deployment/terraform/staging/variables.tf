variable "region" {
  description = "DigitalOcean region for every staging resource."
  type        = string
  default     = "sgp1"

  validation {
    condition     = lower(var.region) == "sgp1"
    error_message = "P2B.3A freezes the initial staging region to sgp1."
  }
}

variable "vpc_name" {
  description = "Deterministic staging-only VPC name."
  type        = string
  default     = "zkd-rag-staging-vpc"
}

variable "vpc_ip_range" {
  description = "Staging-only RFC1918 VPC CIDR, selected by the operator after collision review."
  type        = string
}

variable "app_droplet_name" {
  description = "Deterministic staging App Droplet name."
  type        = string
  default     = "zkd-rag-staging-app"
}

variable "worker_droplet_name" {
  description = "Deterministic staging Worker Droplet name."
  type        = string
  default     = "zkd-rag-staging-worker"
}

variable "database_name" {
  description = "Deterministic staging Managed PostgreSQL cluster name."
  type        = string
  default     = "zkd-rag-staging-db"
}

variable "spaces_bucket_name" {
  description = "Globally unique, lowercase, staging-only Spaces bucket name."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$", var.spaces_bucket_name))
    error_message = "spaces_bucket_name must be a 3-63 character lowercase S3-compatible bucket name."
  }
}

variable "droplet_image" {
  description = "Stable Ubuntu LTS image slug. Application dependencies remain containerized."
  type        = string
  default     = "ubuntu-24-04-x64"
}

variable "app_droplet_size" {
  description = "Initial App Node size; shared CPU performance must be measured after deployment."
  type        = string
  default     = "s-4vcpu-8gb"
}

variable "worker_droplet_size" {
  description = "Initial Worker Node size."
  type        = string
  default     = "s-4vcpu-8gb"
}

variable "database_engine_version" {
  description = "PostgreSQL major version to validate against the frozen PostgreSQL 15 migration baseline."
  type        = string
  default     = "15"
}

variable "database_size_slug" {
  description = "Initial Managed PostgreSQL 1 vCPU / 2 GiB Basic plan slug."
  type        = string
  default     = "db-s-1vcpu-2gb"
}

variable "ssh_key_ids" {
  description = "Existing DigitalOcean SSH key IDs or fingerprints; public keys only."
  type        = list(string)
  default     = []
}

variable "admin_ssh_source_addresses" {
  description = "Administrative public CIDRs allowed to use SSH. Empty means no SSH ingress is declared."
  type        = list(string)
  default     = []
}
