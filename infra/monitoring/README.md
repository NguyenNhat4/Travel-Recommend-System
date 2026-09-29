# Staging Managed Monitoring

This root configures only the staging monitoring environment. It does not contain live-environment resources or a live state path.

## Resources

- Cloud Monitoring dashboard for VM CPU, memory, disk and readiness.
- Alert policies for uptime, CPU, memory, disk and error-level VM logs.
- Cloud Monitoring HTTPS uptime check for the staging readiness endpoint.
- Cloud Logging user metric for error-level Compute Engine logs.
- Optional email notification channel, supplied as a sensitive variable.

The crawler monitor UI is not part of this package. Crawler-specific operational monitoring remains outside the infrastructure monitoring scope.

## Local validation

```bash
bash infra/monitoring/tests/test_staging_layout.sh
terraform -chdir=infra/monitoring fmt -check -recursive
terraform -chdir=infra/monitoring init -backend=false
terraform -chdir=infra/monitoring validate
```

## Staging plan/apply

Create the state bucket and configure credentials outside the repository. Then either use the GitHub Actions staging environment or run:

```bash
terraform -chdir=infra/monitoring init \
  -backend-config=backend.staging.hcl

terraform -chdir=infra/monitoring plan \
  -var-file=staging.tfvars

terraform -chdir=infra/monitoring apply \
  -var-file=staging.tfvars
```

Never commit `backend.staging.hcl`, `staging.tfvars`, state files or generated plans.
