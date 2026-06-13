output "repository_url" {
  description = "Artifact Registry repository URL (without image name)."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.app.repository_id}"
}
