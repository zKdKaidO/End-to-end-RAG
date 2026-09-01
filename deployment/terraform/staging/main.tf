locals {
  app_tag    = "zkd-rag-staging-app"
  worker_tag = "zkd-rag-staging-worker"
}

resource "digitalocean_vpc" "staging" {
  name     = var.vpc_name
  region   = var.region
  ip_range = var.vpc_ip_range
}

resource "digitalocean_droplet" "app" {
  name       = var.app_droplet_name
  region     = var.region
  size       = var.app_droplet_size
  image      = var.droplet_image
  vpc_uuid   = digitalocean_vpc.staging.id
  ssh_keys   = var.ssh_key_ids
  monitoring = true
  backups    = false
  tags       = [local.app_tag]
}

resource "digitalocean_droplet" "worker" {
  name       = var.worker_droplet_name
  region     = var.region
  size       = var.worker_droplet_size
  image      = var.droplet_image
  vpc_uuid   = digitalocean_vpc.staging.id
  ssh_keys   = var.ssh_key_ids
  monitoring = true
  backups    = false
  tags       = [local.worker_tag]
}

resource "digitalocean_database_cluster" "staging" {
  name                 = var.database_name
  engine               = "pg"
  version              = var.database_engine_version
  size                 = var.database_size_slug
  region               = var.region
  node_count           = 1
  private_network_uuid = digitalocean_vpc.staging.id
}

resource "digitalocean_spaces_bucket" "staging" {
  name   = var.spaces_bucket_name
  region = var.region
  acl    = "private"
}

resource "digitalocean_firewall" "app" {
  name = "zkd-rag-staging-app-fw"
  tags = [local.app_tag]

  dynamic "inbound_rule" {
    for_each = var.admin_ssh_source_addresses
    content {
      protocol         = "tcp"
      port_range       = "22"
      source_addresses = [inbound_rule.value]
    }
  }

  # Redis is never Internet-accessible; only the tagged Worker Node may reach it.
  inbound_rule {
    protocol    = "tcp"
    port_range  = "6379"
    source_tags = [local.worker_tag]
  }

  outbound_rule {
    protocol              = "tcp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "udp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
}

resource "digitalocean_firewall" "worker" {
  name = "zkd-rag-staging-worker-fw"
  tags = [local.worker_tag]

  dynamic "inbound_rule" {
    for_each = var.admin_ssh_source_addresses
    content {
      protocol         = "tcp"
      port_range       = "22"
      source_addresses = [inbound_rule.value]
    }
  }

  outbound_rule {
    protocol              = "tcp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "udp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
}
