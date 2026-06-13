terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Enable required GCP APIs
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "monitoring.googleapis.com",
    "logging.googleapis.com",
    "cloudtrace.googleapis.com",
    "iam.googleapis.com",
  ])

  service            = each.key
  disable_on_destroy = false
}

# ── Modules ──────────────────────────────────────────────────────────────────

module "artifact_registry" {
  source = "./modules/artifact_registry"

  project_id  = var.project_id
  region      = var.region
  app_name    = var.app_name
  environment = var.environment
}

module "iam" {
  source = "./modules/iam"

  project_id  = var.project_id
  app_name    = var.app_name
  environment = var.environment
}

module "cloud_run" {
  source = "./modules/cloud_run"

  project_id      = var.project_id
  region          = var.region
  app_name        = var.app_name
  environment     = var.environment
  image           = "${module.artifact_registry.repository_url}/${var.app_name}:${var.image_tag}"
  service_account = module.iam.service_account_email

  depends_on = [
    google_project_service.apis,
    module.artifact_registry,
    module.iam,
  ]
}

module "monitoring" {
  source = "./modules/monitoring"

  project_id    = var.project_id
  app_name      = var.app_name
  environment   = var.environment
  cloud_run_url = module.cloud_run.service_url

  depends_on = [module.cloud_run]
}
