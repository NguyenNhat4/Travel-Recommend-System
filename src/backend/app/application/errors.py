"""Lỗi dùng chung của lớp application, không thuộc một use case riêng."""


class DatabaseUnavailableError(Exception):
    """PostgreSQL không với tới được: kết nối bị từ chối, hết thời gian chờ hoặc rớt giữa chừng.

    Adapter Postgres ném lỗi này thay cho lỗi của driver để `api` ánh xạ thành 503 `DATABASE_UNAVAILABLE`
    (`retryable: true`) mà không phải import driver. Khác với lỗi truy vấn (SQL sai, vi phạm ràng buộc),
    thử lại sau ít phút có thể thành công khi DB hồi phục.
    """
