## Terraform / IaC MVP

This `infra/` folder codifies the long-lived deployment baseline for the single Cloud Run environment used by `showcase-python`.

The design is intentionally small:

- one Cloud Run service
- one Artifact Registry repository
- one runtime service account
- only the minimum IAM needed for the current CD path
- local Terraform state by default

It does **not** try to recreate the broader infrastructure program from `source-node/`.

## Ownership Split

Terraform owns:

- the Artifact Registry repository used by CD
- the Cloud Run service baseline
- the runtime service account attached to Cloud Run
- the minimum IAM bindings needed for the existing deploy identity, including service-scoped Cloud Run deploy/update access

CD still owns:

- building the runtime image
- tagging and pushing the image
- running `python -m alembic upgrade head`
- release-time `gcloud run deploy`
- post-deploy health verification

Out of scope for this MVP:

- PostgreSQL provisioning
- Redis provisioning
- VPC/networking
- GCS buckets
- monitoring/alerting
- Secret Manager resources or secret values
- Terraform Cloud / workspaces
- multi-environment rollout

## Required Variables

Create `infra/terraform.tfvars` from `infra/terraform.tfvars.example` and provide these values:

- `project_id`
- `region`
- `service_name`
- `artifact_registry_repository`
- `runtime_service_account_id`
- `deploy_service_account_email`
- `container_image`

Recommended alignment with the current GitHub CD configuration:

- `project_id` -> `GCP_PROJECT_ID`
- `region` -> `GCP_REGION`
- `service_name` -> `CLOUD_RUN_SERVICE`
- `artifact_registry_repository` -> `ARTIFACT_REGISTRY_REPOSITORY`
- `deploy_service_account_email` -> `DEPLOY_SERVICE_ACCOUNT`

`container_image` is a bootstrap value used when the Cloud Run service is first created or imported. CD continues to roll out release-time images after that.

## Import-First Usage

Prefer importing existing live resources instead of recreating them.

Initialize Terraform:

```bash
terraform -chdir=infra init
```

Import the Artifact Registry repository if it already exists:

```bash
terraform -chdir=infra import google_artifact_registry_repository.app "projects/<project_id>/locations/<region>/repositories/<artifact_registry_repository>"
```

Import the Cloud Run service if it already exists:

```bash
terraform -chdir=infra import google_cloud_run_v2_service.app "projects/<project_id>/locations/<region>/services/<service_name>"
```

Import the runtime service account only if one already exists and should remain canonical:

```bash
terraform -chdir=infra import google_service_account.runtime "projects/<project_id>/serviceAccounts/<runtime_service_account_id>@<project_id>.iam.gserviceaccount.com"
```

After imports, run:

```bash
terraform -chdir=infra plan
```

If a resource does not exist yet, Terraform can create it, but this MVP is designed to import stable live resources first whenever possible.

## Drift With CD

The Cloud Run service resource intentionally does **not** take over release-time image rollout or runtime env injection.

To avoid fighting the existing CD workflow:

- Terraform defines only the stable service baseline
- CD continues to deploy new images and runtime env values
- the Cloud Run resource ignores release-time image/env drift created by normal `gcloud run deploy` usage

That keeps Terraform responsible for long-lived service shape while keeping CD responsible for normal application releases.

## Local State

This MVP uses the default local backend. Do not commit local state files. The repo `.gitignore` is configured to ignore Terraform state and local tfvars files under `infra/`.
