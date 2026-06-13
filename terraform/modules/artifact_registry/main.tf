resource "google_artifact_registry_repository" "app" {
  project       = var.project_id
  location      = var.region
  repository_id = "${var.app_name}-${var.environment}"
  description   = "Docker images for ${var.app_name} (${var.environment})"
  format        = "DOCKER"

  labels = {
    project     = var.app_name
    environment = var.environment
    managed_by  = "terraform"
  }
}
