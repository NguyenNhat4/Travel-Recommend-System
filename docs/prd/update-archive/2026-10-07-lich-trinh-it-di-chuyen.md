# Lịch trình ít di chuyển: gom điểm gần nhau theo ngày, khách sạn gần các điểm

- Ngày: 2026-10-07
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-10-07
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §3 (thêm AC-AGT-04)
- Mã FR/NFR: FR-AGT-03, NFR-REL-01

## Lý do

Khi lập lịch trình, hệ thống chưa xét vị trí của khách sạn và điểm tham quan. Hiện tại:
- khách sạn là khách sạn rẻ nhất;
- hoạt động là các hoạt động rẻ nhất, rải đều vào các ngày.

Vì vậy hai điểm cách nhau gần 50 km (Bắc và Nam Phú Quốc) vẫn có thể nằm cùng một ngày, và khách sạn có thể ở xa mọi
điểm. Không ai muốn đi lại nhiều như vậy.

Dữ liệu đã đủ để làm. Database staging (07/10/2026) có toạ độ cho:
- 12.351/12.476 khách sạn;
- 953/953 điểm tham quan và golf.

Trong một điểm đến, khoảng cách giữa hai điểm tham quan có trung vị 3–15 km và lớn nhất 20–88 km.

Khoảng 270/953 điểm tham quan dùng toạ độ tâm thành phố, phần lớn là tour có đón khách. Ví dụ: Vũng Tàu 48/48, Huế
64/80, Phan Thiết 46/63, Nha Trang 27/88. Các tour này chung một toạ độ, nên nếu tính như vị trí thật thì chúng trông như
"gần nhau nhất" và bị ưu tiên sai. Đề xuất có luật riêng cho trường hợp này.

## Nội dung đề xuất

### `requirements.md` §3 — thêm dòng AC-AGT-04, ngay sau AC-AGT-03

> | **AC-AGT-04** | Lập lịch trình nhiều ngày ở một điểm đến có các điểm tham quan nằm xa nhau, ví dụ *"Phú Quốc 3 ngày
> từ 10/10, 2 người lớn"* | Lịch trình giảm việc đi lại:
> - **Gom theo ngày:** các điểm gần nhau nằm cùng một ngày; không ghép hai điểm xa nhau vào một ngày khi còn cách ghép gần
>   hơn.
> - **Chọn điểm:** khi có nhiều điểm hơn số chỗ trong lịch, ưu tiên các điểm gần cụm chính; điểm ở xa bị bỏ trước.
> - **Khách sạn:** một khách sạn cho cả chuyến, nằm gần các điểm đã chọn.
> - **Gần trước, rẻ sau:** hai lựa chọn chênh nhau dưới 2 km coi như gần ngang nhau, khi đó chọn cái rẻ hơn.
> - **Không đổi các luật đang có:** sản phẩm Search vẫn ưu tiên hơn Recommendation, xếp theo giờ bay (AC-AGT-02), tối đa
>   2 hoạt động một ngày, hoạt động cả ngày đứng riêng. Ngày đến và ngày về bị giới hạn giờ thì nhận điểm gần khách sạn
>   nhất.
> - **Nói cho người dùng:** câu trả lời có một câu nêu tiêu chí này.
> - **Chưa rõ vị trí:** gồm hai trường hợp:
>   - sản phẩm thiếu toạ độ;
>   - sản phẩm mang toạ độ tâm thành phố: toạ độ có từ 4 chữ số thập phân trở xuống **và** dùng chung cho từ 5 sản phẩm
>     trở lên trong cùng điểm đến.
>
>   Sản phẩm chưa rõ vị trí vẫn được xếp, nhưng đứng sau sản phẩm rõ vị trí. Không sản phẩm nào rõ vị trí thì xếp như
>   trước.
>
> Khoảng cách tính theo đường chim bay giữa hai toạ độ. Lịch trình chưa hiện số km. |

FR-AGT-03 giữ nguyên câu chữ. Phần "thời gian di chuyển ước tính" làm ở đợt sau (xem dưới).

### Ngoài phạm vi đợt này

Các mục dưới đây sẽ có đề xuất riêng:
- **Quãng đường đường bộ thật** (OSRM tự host) và **hiện km/phút** cho từng ngày. Cần thêm service, đổi contract
  `ItineraryDay` và sửa widget.
- **Nâng hạng khách sạn theo ngân sách:** có ngân sách thì nâng dần lên hạng sao cao hơn khi tổng tiền vẫn trong ngân
  sách.
- **Đánh dấu toạ độ tâm thành phố ở nguồn:** luật "chưa rõ vị trí" ở trên chỉ là cách nhận diện tạm. Team Data nên ghi
  rõ độ chính xác của toạ độ, ví dụ `attributes.geoPrecision = "city"`.

## Thay đổi source sau khi chốt

- `src/backend/app/domain/itinerary/geo.py` (mới): haversine, điểm mốc (medoid), mức khoảng cách 2 km, nhận diện toạ
  độ tâm thành phố.
- `src/backend/app/domain/itinerary/planning.py` — `compose_plan`:
  - chọn hoạt động theo khoảng cách tới mốc;
  - chọn khách sạn theo khoảng cách trung bình tới các hoạt động;
  - gom từng cặp điểm gần nhau vào một ngày.
- `src/backend/app/agents/steps/composition.py`, `narration.py`, `prompts.py`: câu báo tiêu chí (warning
  `PLAN_CRITERIA`).
- Test: `src/backend/tests/unit/domain/test_itinerary_composition.py`, test mới cho `geo.py`,
  `src/backend/tests/unit/agents/test_itinerary_runtime.py`.
- Spec:
  - `docs/spec/agent/nghiep-vu/xep-lich.md`;
  - `docs/spec/agent/nghiep-vu/glossary.md`;
  - `docs/spec/agent/langgraph-nodes.md` §5;
  - `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` §2.7.
- Không đổi contract OpenAPI và không đổi DDL.
