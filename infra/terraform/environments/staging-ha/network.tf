# VM của nhóm HA không có IP public (chỉ nhận traffic qua load balancer), nên mọi lời gọi ra ngoài đi qua Cloud NAT:
# Stripe (thanh toán), Cohere (embed truy vấn /search), LLM của trợ lý, cr.weaviate.io (image Weaviate).
# Đặt create_nat = false nếu VPC đã có Cloud NAT cho region này (mỗi router/NAT chỉ một cặp trên một mạng/region).
resource "google_compute_router" "nat" {
  count   = var.create_nat ? 1 : 0
  name    = "${var.name_prefix}-router"
  region  = var.region
  network = var.network
}

resource "google_compute_router_nat" "egress" {
  count                              = var.create_nat ? 1 : 0
  name                               = "${var.name_prefix}-nat"
  router                             = google_compute_router.nat[0].name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
  min_ports_per_vm                   = 256 # Stripe + Cohere + LLM song song, 2 worker mỗi VM

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}
