terraform {
  backend "gcs" {
    # Set via -backend-config or environment:
    # terraform init -backend-config="bucket=my-tf-state-bucket"
    # or TF_VAR_backend_bucket
    bucket = "REPLACE_WITH_YOUR_TF_STATE_BUCKET"
    prefix = "healthcheck-api/state"
  }
}
