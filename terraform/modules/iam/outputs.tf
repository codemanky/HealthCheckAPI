output "service_account_email" {
  description = "Service account email for Cloud Run."
  value       = google_service_account.app.email
}
