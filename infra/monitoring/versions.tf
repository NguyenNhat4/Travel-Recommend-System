terraform {
  required_version = ">= 1.6.0, < 2.0.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }

  # The bucket and IAM are preflight prerequisites. They are intentionally
  # supplied by backend config so this root cannot silently create its own
  # state store or mix state with another environment.
  backend "gcs" {}
}
