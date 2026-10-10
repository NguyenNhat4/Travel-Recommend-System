terraform {
  required_version = ">= 1.9.0, < 2.0.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    # update_policy.min_ready_sec của MIG chỉ có ở google-beta (google 6.50 chưa có). Chỉ dùng cho đúng một resource.
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 6.0"
    }
  }
}
