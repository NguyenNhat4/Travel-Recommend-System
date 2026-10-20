terraform {
  # Bucket/prefix được truyền bằng -backend-config trong lệnh triển khai và workflow,
  # nhưng backend type phải được khai báo để Terraform không rơi về local state.
  backend "gcs" {}
}
