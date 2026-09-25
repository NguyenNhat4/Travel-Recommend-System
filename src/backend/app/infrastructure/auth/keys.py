"""Nạp cặp khoá RS256 (auth §10.2, §19). Khoá riêng chỉ ở FastAPI, không trong repo, không trong image.

Thiếu file khoá:
  * production → ném lỗi, backend không khởi động (fail closed).
  * development/test → sinh cặp khoá tạm trong bộ nhớ và cảnh báo. Mọi token hết hiệu lực khi
    restart; BFF nhận 401 và đưa người dùng về trạng thái phiên hết hạn. Muốn giữ phiên qua restart
    thì sinh khoá bằng `make jwt-keys`.
"""
from __future__ import annotations

import logging
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

logger = logging.getLogger(__name__)


def generate_rsa_pem_pair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    public_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    return private_pem, public_pem


def load_rsa_pem_pair(private_path: str, public_path: str, *, base_dir: Path, allow_ephemeral: bool) -> tuple[str, str]:
    def resolve(raw: str) -> Path:
        path = Path(raw)
        return path if path.is_absolute() else base_dir / path

    private_file, public_file = resolve(private_path), resolve(public_path)
    if private_file.is_file() and public_file.is_file():
        return private_file.read_text(), public_file.read_text()
    if not allow_ephemeral:
        raise RuntimeError(
            "Thiếu JWT_PRIVATE_KEY_PATH/JWT_PUBLIC_KEY_PATH; production không được dùng khoá tạm."
        )
    logger.warning("auth.jwt.ephemeral_keys — thiếu file khoá, dùng cặp khoá tạm (token mất hiệu lực khi restart)")
    return generate_rsa_pem_pair()
