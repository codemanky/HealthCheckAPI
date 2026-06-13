resource "google_service_account" "app" {
  project      = var.project_id
  account_id   = "${var.app_name}-${var.environment}-sa"
  display_name = "${var.app_name} (${var.environment}) Service Account"
  description  = "Least-privilege service account for Cloud Run workload"
}

resource "google_project_iam_member" "log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.app.email}"
}

resource "google_project_iam_member" "metric_writer" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.app.email}"
}

resource "google_project_iam_member" "trace_agent" {
  project = var.project_id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${google_service_account.app.email}"
}
