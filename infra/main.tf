locals {
  deploy_service_account_member = "serviceAccount:${var.deploy_service_account_email}"

  common_labels = merge(
    {
      managed-by = "terraform"
      service    = var.service_name
    },
    var.labels,
  )
}

resource "google_artifact_registry_repository" "app" {
  project       = var.project_id
  location      = var.region
  repository_id = var.artifact_registry_repository
  description   = "Docker images for ${var.service_name}"
  format        = "DOCKER"
  labels        = local.common_labels
}

resource "google_service_account" "runtime" {
  project      = var.project_id
  account_id   = var.runtime_service_account_id
  display_name = "${var.service_name} runtime"
}

resource "google_service_account_iam_member" "deploy_can_use_runtime_service_account" {
  service_account_id = google_service_account.runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = local.deploy_service_account_member
}

resource "google_artifact_registry_repository_iam_member" "deploy_writer" {
  project    = var.project_id
  location   = var.region
  repository = google_artifact_registry_repository.app.repository_id
  role       = "roles/artifactregistry.writer"
  member     = local.deploy_service_account_member
}

resource "google_cloud_run_v2_service" "app" {
  project  = var.project_id
  name     = var.service_name
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"
  client   = "terraform"
  labels   = local.common_labels

  template {
    service_account = google_service_account.runtime.email
    timeout         = "${var.request_timeout_seconds}s"

    scaling {
      min_instance_count = var.min_instance_count
      max_instance_count = var.max_instance_count
    }

    max_instance_request_concurrency = var.max_instance_request_concurrency

    containers {
      image = var.container_image

      ports {
        container_port = var.container_port
      }

      resources {
        limits = {
          cpu    = var.cpu
          memory = var.memory
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [
      client,
      client_version,
      template[0].containers[0].env,
      template[0].containers[0].image,
      template[0].labels,
      template[0].annotations,
      traffic,
    ]
  }
}

resource "google_cloud_run_v2_service_iam_member" "deploy_developer" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.app.name
  role     = "roles/run.developer"
  member   = local.deploy_service_account_member
}

resource "google_cloud_run_v2_service_iam_member" "deploy_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.app.name
  role     = "roles/run.invoker"
  member   = local.deploy_service_account_member
}
