variable "project_id" {
  description = "GCP project ID where resources will be deployed."
  type        = string
}

variable "region" {
  description = "GCP region for resource deployment."
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "app_name" {
  description = "Application name used for resource naming."
  type        = string
  default     = "healthcheck-api"
}

variable "image_tag" {
  description = "Docker image tag to deploy to Cloud Run."
  type        = string
  default     = "latest"
}
