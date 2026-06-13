output "cloud_run_url" {
  description = "Public URL of the deployed Cloud Run service."
  value       = module.cloud_run.service_url
}

output "artifact_registry_url" {
  description = "Artifact Registry repository URL for Docker images."
  value       = module.artifact_registry.repository_url
}

output "service_account_email" {
  description = "Service account email used by Cloud Run."
  value       = module.iam.service_account_email
}
