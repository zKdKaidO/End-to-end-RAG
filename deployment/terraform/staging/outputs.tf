output "staging_vpc_id" {
  description = "VPC identifier used by the staging Droplets and Managed PostgreSQL cluster."
  value       = digitalocean_vpc.staging.id
}

output "app_private_ipv4" {
  description = "Private App Node address to use for Redis private binding and worker connectivity."
  value       = digitalocean_droplet.app.ipv4_address_private
}

output "worker_private_ipv4" {
  description = "Private Worker Node address for operational validation."
  value       = digitalocean_droplet.worker.ipv4_address_private
}

output "spaces_bucket_name" {
  description = "Staging-only canonical Spaces bucket name."
  value       = digitalocean_spaces_bucket.staging.name
}

output "managed_postgresql_cluster_id" {
  description = "Managed PostgreSQL cluster identifier; obtain private/TLS connection details from the provider after creation."
  value       = digitalocean_database_cluster.staging.id
}
