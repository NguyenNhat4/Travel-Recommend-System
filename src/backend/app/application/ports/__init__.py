"""Port (interface) mà infrastructure phải hiện thực. Application chỉ phụ thuộc vào package này.

Hai nhóm port, tách file vì phục vụ hai chiều khác nhau của cùng một hệ:

* `cdp_client` — chiều **ghi** về CDP và đọc profile: `CdpClient`, `PurchaseEvent`, `BrowseEvent`…
  Dùng cho checkout, ghi hành vi duyệt web và bù trừ khi booking lỗi.
* `recsys` — chiều **đọc** cho search và gợi ý: `UnitIndex`, `VectorStorePort`, `EmbedderPort`,
  `CdpClientPort`. Re-export ở đây để `from ...application.ports import UnitIndex` vẫn viết được
  như khi `ports` còn là một module đơn.
"""

from .recsys import CdpClientPort, EmbedderPort, UnitIndex, VectorStorePort

__all__ = ["CdpClientPort", "EmbedderPort", "UnitIndex", "VectorStorePort"]
