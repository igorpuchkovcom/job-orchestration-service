output "artifact_registry_repository" {
  description = "Artifact Registry repository name."
  value       = google_artifact_registry_repository.app.repository_id
}

output "artifact_registry_image_repository" {
  description = "Base image repository path used by CD."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_registry_repository}/${var.service_name}"
}

output "runtime_service_account_email" {
  description = "Runtime service account attached to the Cloud Run service."
  value       = google_service_account.runtime.email
}

output "cloud_run_service_name" {
  description = "Cloud Run service name."
  value       = google_cloud_run_v2_service.app.name
}

output "cloud_run_service_uri" {
  description = "Cloud Run service URI."
  value       = google_cloud_run_v2_service.app.uri
}
