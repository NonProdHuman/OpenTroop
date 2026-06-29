terraform {

  cloud {
    hostname     = "couvrette.scalr.io"
    organization = "env-v0palb6a7sk6803nh"

    workspaces {
      name = "opentroop-dev"
    }
  }

  required_version = "~> 1.8"

  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 5.0"
    }
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    neon = {
      source  = "kislerdm/neon"
      version = "~> 0.13"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}
