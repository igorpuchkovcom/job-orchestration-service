variable "project_id" {
  description = "GCP project ID that hosts the Cloud Run service and Artifact Registry repository."
  type        = string
}

variable "region" {
  description = "Single GCP region for the Cloud Run service and Artifact Registry repository."
  type        = string
}

variable "service_name" {
  description = "Canonical Cloud Run service name."
  type        = string
  default     = "job-orchestration-service"
}

variable "artifact_registry_repository" {
  description = "Artifact Registry Docker repository name used by CD."
  type        = string
  default     = "job-orchestration-service"
}

variable "runtime_service_account_id" {
  description = "Account ID for the Cloud Run runtime service account."
  type        = string
  default     = "job-orchestration-service-runtime"
}

variable "deploy_service_account_email" {
  description = "Email of the existing deploy identity used by GitHub Actions CD."
  type        = string
}

variable "container_image" {
  description = "Bootstrap image reference used when the Cloud Run service is first created or imported. CD continues to roll out release-time images."
  type        = string
}

variable "container_port" {
  description = "Container port exposed by the service."
  type        = number
  default     = 8000
}

variable "request_timeout_seconds" {
  description = "Cloud Run request timeout in seconds."
  type        = number
  default     = 300
}

variable "min_instance_count" {
  description = "Minimum number of Cloud Run instances."
  type        = number
  default     = 0
}

variable "max_instance_count" {
  description = "Maximum number of Cloud Run instances."
  type        = number
  default     = 2
}

variable "max_instance_request_concurrency" {
  description = "Maximum concurrent requests per instance."
  type        = number
  default     = 80
}

variable "cpu" {
  description = "CPU limit for the application container."
  type        = string
  default     = "1"
}

variable "memory" {
  description = "Memory limit for the application container."
  type        = string
  default     = "512Mi"
}

variable "labels" {
  description = "Optional labels applied to long-lived resources."
  type        = map(string)
  default     = {}
}
