# Lấy đủ điểm tham quan của điểm đến để lịch gần và có điểm miễn phí

- Ngày: 2026-10-08
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: chờ chốt
- Chốt bởi / ngày:
- PRD bị ảnh hưởng: `docs/prd/architecture.md` §3 (nguồn sản phẩm của lịch trình); `docs/prd/requirements.md` §3 (AC-AGT-04)
- Mã FR/NFR: FR-AGT-02, FR-AGT-03, FR-AGT-04, NFR-REL-01, AC-AGT-04

## Lý do

Hội thoại thật ngày 08/10/2026: "đi HCM 3 ngày 2 đêm, 2 vợ chồng 1 đứa con". Lịch ra phải đi 36,5 km, gồm 3 vé Grand Park
(Thủ Đức, cách trung tâm 17 km) và 3 tour múa rối kèm du thuyền gần như giống hệt nhau. Tour "buổi tối" bị xếp vào buổi
sáng, và không có chỗ miễn phí nào như Chợ Bến Thành hay Bưu điện.

1. **Quá ít điểm để chọn.** Lịch chỉ lấy điểm tham quan từ Search. Search tìm theo nghĩa của câu ("hoạt động tham quan gia
   đình trẻ em") và chỉ trả **7 kết quả nằm ở 2 địa điểm**. Luật ít di chuyển (AC-AGT-04) có tốt đến đâu cũng phải đưa
   khách ra Thủ Đức.
2. **Điểm miễn phí không bao giờ được tìm thấy.** Catalog TP.HCM có 9 điểm tham quan tự do còn mở, có toạ độ chính xác,
   phần lớn ở Quận 1. Search chỉ trả chúng khi gõ đúng tên ("chợ bến thành"). Gõ "tham quan" chỉ ra 3 kết quả, gõ "đi dạo
   miễn phí" ra 5, không có điểm miễn phí nào trong đó.
3. **Một địa điểm bán nhiều loại vé.** 4 vé Grand Park là 4 sản phẩm khác nhau nhưng cùng một nơi, nên lịch có thể đi
   Grand Park ở hai ngày khác nhau.
4. **Lịch chỉ có buổi sáng và buổi chiều**, nên tour buổi tối bị xếp nhầm vào buổi sáng.

Phần sửa không lệch PRD đã làm xong (`history/2026-10-08-search-agent-du-tham-so-va-span-tool.md`): search khách sạn lấy đủ
số khách và 50 kết quả, không tự tìm golf, điểm miễn phí được tính 0 đ. Khi thử lại, quãng đường còn 33,1 km. Hoạt động vẫn
như cũ vì nguyên nhân 1–4 ở trên.

## Nội dung đề xuất

### 1. `docs/prd/architecture.md` §3 — thêm nguồn sản phẩm Catalog

Hiện tại:

> Mọi thông tin về `productId`, `title`, `price`, `imageUrl` bắt buộc phải được lấy nguyên trạng từ kết quả trả về của
> công cụ truy xuất (`ToolCatalogSearch`): Search, Recommendation, hoặc Similar (`getSimilarProducts`) khi đổi một sản
> phẩm đã hiển thị.

Thay bằng:

> Mọi thông tin về `productId`, `title`, `price`, `imageUrl` bắt buộc phải được lấy nguyên trạng từ kết quả trả về của
> công cụ truy xuất (`ToolCatalogSearch`): Search, Recommendation, Similar (`getSimilarProducts`) khi đổi một sản phẩm đã
> hiển thị, hoặc danh sách điểm tham quan của điểm đến từ Catalog (`GET /products`), do hệ thống tự lấy theo luật, không
> qua LLM.

### 2. `docs/prd/requirements.md` §3, AC-AGT-04 — thêm vào sau câu "Lịch luôn xếp đủ số điểm…"

> Điểm tham quan được chọn từ kết quả Search và từ toàn bộ điểm tham quan còn mở của điểm đến trong catalog, kể cả điểm
> tham quan tự do (tính 0 đ). Cùng mức khoảng cách thì kết quả Search được ưu tiên. Mỗi địa điểm (cùng toạ độ) chỉ vào lịch
> một lần, dù có nhiều loại vé. Tour hoặc hoạt động diễn ra buổi tối (tên có "evening", "night", "tối", "đêm", "dinner
> cruise") không xếp vào buổi sáng hay buổi chiều; chúng được gợi ý riêng như gói nhiều ngày.

Không lấy thêm khi người dùng loại điểm tham quan, hoặc khi người dùng đã nêu đích danh một hoạt động bắt buộc.

### Không đổi

Grounding 100% (FR-AGT-04, NFR-REL-01) giữ nguyên: sản phẩm từ Catalog là sản phẩm thật, qua cùng bước kiểm tra như Search.
LLM không thấy và không gọi công cụ Catalog.

## Thay đổi source sau khi chốt

- `src/backend/app/application/itinerary/attraction_pool.py` (mới, theo mẫu `flights.py`): lấy mọi trang
  `list_products(destination, taxonomy=attraction, availableOnly=true, sort=popular)`, có timeout, lỗi thì bỏ qua.
- `src/backend/app/agents/nodes.py` `tool_node`: chạy song song với search và tra vé bay; kết quả vào `tool_results` với
  tên `list_products`.
- `src/backend/app/application/itinerary/retrieval.py`: sản phẩm từ Catalog mang nguồn `catalog`.
- `src/backend/app/domain/itinerary/planning.py`: thứ tự hoạt động (gần trước, cùng mức gần thì Search trước Catalog);
  khoá địa điểm theo toạ độ; tour buổi tối ra `searchResults`.
- Spec: `docs/spec/agent/nghiep-vu/tim-ung-vien.md`, `xep-lich.md`, `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`.
- Test: unit domain (4 vé Grand Park → 1, tour tối), unit agent (gọi Catalog theo luật), golden case cho hội thoại TP.HCM.
