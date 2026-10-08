# Postgres + Patroni cho tầng DB tự failover (docs/plan/2026-10-07-ha-vung-crawler-rolling.md §2).
# Cùng image gốc với primary/replica hiện tại (cùng major, cùng extension) để dữ liệu clone sang chạy được ngay.
ARG PG_IMAGE=pgvector/pgvector:0.8.6-pg18-bookworm
FROM ${PG_IMAGE}

ARG PATRONI_VERSION=4.1.0
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv curl ca-certificates \
    && python3 -m venv /opt/patroni \
    && /opt/patroni/bin/pip install --no-cache-dir "patroni[etcd3]==${PATRONI_VERSION}" "psycopg[binary]>=3.1" \
    && rm -rf /var/lib/apt/lists/*

COPY patroni.yml bootstrap-clone.yml /opt/vota/patroni/
COPY entrypoint.sh clone-from-primary.sh cluster_probe.py /opt/vota/
RUN chmod 0755 /opt/vota/entrypoint.sh /opt/vota/clone-from-primary.sh /opt/vota/cluster_probe.py

# Dữ liệu nằm ngoài image, trên đĩa persistent mount vào /var/lib/postgresql.
ENV PATRONI_DATA_DIR=/var/lib/postgresql/18/patroni
EXPOSE 5432 8008
ENTRYPOINT ["/opt/vota/entrypoint.sh"]
