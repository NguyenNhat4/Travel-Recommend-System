// Backend configuration is supplied at init time:
// terraform init -backend-config=backend.staging.hcl
// The real backend file must not be committed. Use a prefix different from
// infra/monitoring (monitoring/staging) so the two roots never share state.
terraform {
  backend "gcs" {}
}
