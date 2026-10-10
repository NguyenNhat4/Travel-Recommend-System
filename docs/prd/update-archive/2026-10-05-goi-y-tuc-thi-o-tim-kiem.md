# Gợi ý tức thì khi gõ ở ô tìm kiếm (instant search)

- Ngày: 2026-10-05
- Người đề xuất: mihhquan / Claude
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: mihhquan, 2026-10-05
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1.2 và §3; `docs/prd/user-flow.md` §2 và §3.1; `docs/prd/api-contract.md` §2.3
- Mã FR/NFR: mới — đề nghị cấp **FR-SRC-05** và **AC-SRC-02**; chịu ngân sách thời gian của NFR-PERF-01

## Lý do

Ô tìm kiếm ở hero trang chủ và ở đầu trang `/search` hiện chỉ tìm khi nhấn Enter. Trong lúc gõ người dùng không thấy gì, nên không biết hệ thống có điểm đến hay dịch vụ mình đang nghĩ tới hay không, và phải gõ hết câu rồi mới biết.

PRD chưa có yêu cầu nào về gợi ý khi gõ. `docs/spec/product.md` §4.2.1 còn ghi rõ "MVP: không autocomplete, Enter là tìm". Vì vậy đây là thêm hành vi so với PRD.

Không dùng lại API tìm kiếm hiện có cho việc này: mỗi lượt `POST /search` gọi Cohere và Weaviate (p95 đo ngày 01/10/2026 trên VM là 4,0 giây) và ghi một event `search` vào lịch sử người dùng. Gọi theo từng phím sẽ chậm và làm lệch gợi ý cá nhân hóa.

## Nội dung đề xuất

### 1. `requirements.md` §1.2 — thêm FR-SRC-05

Hiện tại: mục kết thúc ở FR-SRC-04.

Thêm sau FR-SRC-04:

> - **FR-SRC-05 (Gợi ý tức thì khi gõ):** Ô tìm kiếm ở trang chủ và ở trang `/search` hiển thị gợi ý ngay trong lúc người dùng gõ, không cần nhấn phím nào khác.
>   - Gợi ý chia theo loại: điểm đến, khách sạn, vé tham quan, sân golf, combo. Mỗi dòng có biểu tượng của loại và tên loại; phần chữ trùng với từ đang gõ được in đậm. Không gợi ý vé máy bay (vé máy bay chỉ tìm ở `/flights`, như FR-SRC-03).
>   - So khớp theo đầu từ, không phân biệt dấu và hoa thường: gõ "ha" thấy "Hà Nội", "Hạ Long".
>   - Tối đa 8 gợi ý. Cuối danh sách luôn có nút "Xem tất cả kết quả cho …" dẫn sang `/search` với đúng chữ đang gõ.
>   - Chọn một điểm đến thì sang `/search` với tên điểm đến đó; chọn một sản phẩm thì mở trang chi tiết sản phẩm.
>   - Kiểm soát số lượt gọi: chỉ gợi ý khi có ít nhất 2 ký tự chữ hoặc số; chuỗi rỗng hoặc toàn khoảng trắng thì không gọi; lượt gọi cũ bị huỷ khi người dùng gõ tiếp; kết quả của từ đã gõ gần đây được dùng lại mà không gọi lại.
>   - Khi ô còn trống và đang được chọn: hiện "Tìm kiếm gần đây" (tối đa 5, lưu trên trình duyệt của người dùng, có nút xóa) và "Từ khoá phổ biến" (danh sách cố định).
>   - Gợi ý lấy từ catalog đang phục vụ, không do LLM sinh. Gõ để xem gợi ý không được tính là một lượt tìm kiếm trong lịch sử hành vi (không ghi event `search`).

### 2. `requirements.md` §3 — thêm AC-SRC-02

Thêm một dòng sau AC-SRC-01:

> | **AC-SRC-02** | Người dùng gõ "Ha" vào ô tìm kiếm ở trang chủ | Không cần nhấn Enter, danh sách tối đa 8 gợi ý hiện ra, chia theo loại, có điểm đến Hà Nội và Hạ Long, phần "Ha"/"Hà"/"Hạ" in đậm, cuối danh sách có "Xem tất cả kết quả cho "Ha"". Gõ một ký tự hoặc toàn khoảng trắng thì không có lượt gọi nào. Ô trống khi được chọn thì hiện tìm kiếm gần đây và từ khoá phổ biến. API gợi ý phản hồi trong 250 ms ở p95 (NFR-PERF-01). |

### 3. `user-flow.md` §2 — bảng route

Hiện tại (dòng `/`): "Hero Search Bar, Category Nav, Personalized Carousels, Trending Destinations".
Thay bằng: "Hero Search Bar **(gợi ý tức thì khi gõ)**, Category Nav, Personalized Carousels, Trending Destinations".

Hiện tại (dòng `/search`): "Query Header, Tab nhóm (…), …".
Thay bằng: "Query Header, **ô tìm kiếm có gợi ý tức thì**, Tab nhóm (…), …" (phần còn lại giữ nguyên).

### 4. `user-flow.md` §3.1 — luồng tìm kiếm

Hiện tại: `A[Người dùng tại Trang chủ] --> B[Nhập câu truy vấn tự nhiên] --> C{Loại truy vấn?}`.

Thêm một nhánh giữa B và C:

> B → "Gợi ý tức thì hiện trong lúc gõ". Từ đó có ba lối: chọn một sản phẩm → mở `/products/:id`; chọn một điểm đến hoặc "Xem tất cả kết quả" → trang `/search`; nhấn Enter → tiếp tục luồng tìm kiếm như cũ (C).

### 5. `api-contract.md` §2.3 — thêm ví dụ minh hoạ

Thêm sau đoạn mô tả `POST /api/v1/search`:

> - **Gợi ý khi gõ:** `GET /api/v1/search/suggestions?q=ha&limit=8` — trả tối đa 10 gợi ý, mỗi gợi ý có loại (`destination` hoặc `product`), nhãn hiển thị và, với sản phẩm, `productId` cùng `taxonomy`. Không cần đăng nhập, không ghi hành vi. Hình dạng chính xác ở `src/shared/contracts/openapi.yaml`.

## Thay đổi source sau khi chốt

- `docs/prd/requirements.md`, `docs/prd/user-flow.md`, `docs/prd/api-contract.md`: cập nhật theo nội dung đã chốt (làm trước).
- Contract: `src/shared/contracts/paths/search.yaml`, `schemas/search.yaml`, `openapi.yaml` (thêm `GET /search/suggestions`, bump 1.13.0 → 1.14.0, chỉ thêm nên tương thích ngược); mock trong `src/shared/mocks/search/` và `index.json`; sinh lại `src/frontend/src/types/api.gen.ts`.
- Backend: `src/backend/app/domain/search/suggest.py`, `app/application/search/suggest.py` (mới); `app/api/v1/routes/search.py`, `app/api/deps.py`, `app/main.py`; `src/backend/README.md`. Không thêm bảng, không đổi DDL.
- Frontend: `src/frontend/src/services/suggest.ts`, `src/frontend/src/features/search/instant/` (mới); `src/frontend/src/components/home/HomeView.tsx`, `src/frontend/src/components/common/SearchBox.tsx`.
- Spec: `docs/spec/product.md` §4.2.1, `docs/spec/hop-dong-tich-hop-frontend.md` §4.1 và §4.2, `docs/spec/hop-dong-tich-hop-search-recommendation.md` §3.
- Test: unit và contract ở `src/backend/tests/`, unit ở `src/frontend/tests/unit/`.

## Ghi chú khi áp dụng

- Quy ước lỗi của endpoint: tham số sai trả `422 VALIDATION_ERROR` (như mọi route FastAPI khác của repo, `api/errors.py`), không phải `400`; `q` ngắn dưới 2 ký tự chữ/số trả `200` rỗng.

## Chưa làm trong đề xuất này

- Từ khoá phổ biến theo số liệu tìm kiếm thật (hiện là danh sách cố định).
- Giới hạn tần suất gọi phía máy chủ cho API gợi ý.
- Sửa lỗi chính tả trong gợi ý.
