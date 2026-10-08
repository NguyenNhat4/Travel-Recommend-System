# RecSys bám sở thích — điều tra gate G2 và đo tổ hợp triển khai (WP4)

- Ngày chạy: 2026-10-08 (sau khi người dùng chốt G1, G3, G4 và **từ chối** G2)
- Phục vụ: FR-REC-01, FR-REC-02, FR-REC-04 (`docs/prd/requirements.md` §1.3), AC-REC-02
- Plan: `docs/plan/2026-10-08-ban-giao-recsys-bam-so-thich.md` WP3 (G2), WP4
- Số nền và phương pháp: `eval-2026-10-08-recsys-so-thich-ci.md`; mốc engine: `eval-2026-10-08-recsys-so-thich-moc-moi.md`
- Quyết định: `docs/spec/bench/recsys-bam-so-thich-quyet-dinh.md`
- Kết quả gốc: `src/evaluation/recsys_bench/theme_study/results/2026-10-08-g2-wp4/`
- Môi trường, dữ liệu, parity: giống hai report trên (`vota_prodcopy` 08/10 01:49, vector `.npy` của gói bàn giao,
  `parity_mismatch_llbo200 = 0`)

## 1. Vì sao có lượt đo này

Người dùng chốt: **G1** giữ ngưỡng điểm ước lượng ở **0,04** · **G3** chọn **P2 + F14c** (pop 0,35) · **G4** làm ô khám phá
B · **G2 chưa chấp nhận được** (mức giảm nexttrip).

G1 ở 0,04 thì cả bốn ứng viên đạt tiêu chí temporal (F7 −0,0284 · F14c −0,0335 · F14 −0,0348 · F13a −0,0374). Nhưng G2 và
G3 **xung đột**: F14c có nexttrip h@20 −0,0381. Lượt này trả lời ba câu:

1. Mức giảm nexttrip là chi phí thật hay hệ quả của dữ liệu? (§2)
2. Có cách nào giảm nó mà vẫn giữ F14c? (§3)
3. Tổ hợp sẽ triển khai (P2 + F14c + ô B) thực sự đo được bao nhiêu, kể cả thời gian xếp hạng? (§4, §5)

## 2. Mức giảm nexttrip: không phải artefact độ phổ biến, nhưng split thật **không đo được lợi ích**

### 2.1 Ba giả thuyết "có thể nhắm vào nhóm nào" — cả ba đều sai

Dùng `theme_study/loss_analysis.py` trên kết quả từng khách, so production với P2+F14c trên nexttrip (n = 1.835):

**(a) Mất ở nhóm target bán chạy?** Không.

| Phân vị độ phổ biến của target | n | production | P2+F14c | chênh | % tổng mất |
|---|---:|---:|---:|---:|---:|
| [0; 0,5) | 1.672 | 0.0730 | 0.0377 | −0,0353 | **84 %** |
| [0,75; 0,9) | 5 | 0.2000 | 0.2000 | +0,0000 | 0 % |
| [0,9; 1,0] | 158 | 0.1329 | 0.0633 | −0,0696 | 16 % |

84 % mức mất nằm ở target thuộc **nửa dưới** độ phổ biến. Tỷ lệ mất tương đối gần như nhau ở hai nhóm (−48 % so với
−52 %). Vậy không thể gọi đây là "chỉ mất món bán chạy".

**(b) Mất tập trung ở khách ít lịch sử?** Không — mức mất *tăng* theo lịch sử:

| số event trong train | n | production | P2+F14c | chênh |
|---|---:|---:|---:|---:|
| [0; 3) | 62 | 0.0484 | 0.0323 | −0,0161 |
| [3; 6) | 658 | 0.0684 | 0.0350 | −0,0334 |
| [6; 12) | 713 | 0.0884 | 0.0463 | −0,0421 |
| [12; ∞) | 402 | 0.0821 | 0.0398 | −0,0423 |

→ Không gate được theo số event.

**(c) Mất tập trung ở khách có lịch sử tản mát?** Không. Độ nhất quán hướng của lịch sử (`trip_coherence`, mean resultant
length của các vector chuyến **sau khi trừ vector trung bình catalog** — trong không gian thô của e5-small cả 1.835 khách
đều ≥ 0,8 nên thước đo vô dụng, phải center trước):

| coherence | n | production | P2+F14c | chênh | nEvents trung vị |
|---|---:|---:|---:|---:|---:|
| [0; 0,4) | 54 | 0.1111 | 0.0741 | −0,0370 | 20 |
| [0,4; 0,6) | 656 | 0.0899 | 0.0442 | −0,0457 | 12 |
| [0,6; 0,8) | 599 | 0.0751 | 0.0401 | −0,0351 | 6 |
| [0,8; 1,0] | 526 | 0.0646 | 0.0323 | −0,0323 | 3 |

→ Mức mất đều khắp (−0,032 … −0,046), không có nhóm nào để nhắm vào. **Không có đường giảm thiệt hại bằng cách bật / tắt
công thức theo đặc điểm khách.**

Một điều đúng và quan trọng: **100 % khách bị lật từ hit sang miss đều không có chuyến mở** (`shareOpenTrip = 0,0`), còn
42 % khách giữ được hit là khách có chuyến mở. Đúng thiết kế — công thức chỉ chạm nhánh không có chuyến mở.

### 2.2 Nhưng split thật không chứa tín hiệu sở thích nào

Đọc bộ sinh event (`src/data_collection/seed/seed_histories.py`):

```python
# dòng 344–346, vòng lặp chuyến của MỘT khách
for _ in range(n_trips):
    dest, verticals = plan_trip(w, rng, home)        # tham số duy nhất của khách là `home`
# dòng 160–161
def destination(self, rng: random.Random) -> str:     # KHÔNG có tham số khách
    return self.dest_names[... rng.random() * self.dest_cum[-1] ...]
```

Điểm đến của mỗi chuyến được bốc từ một phân phối **toàn cục** (trọng số theo số sản phẩm của điểm đến), **không phụ thuộc
khách**. `home` chỉ dùng để kiểm tra có tuyến bay (`w.has(dest, "flight", home)`). Nói cách khác: trong dữ liệu seed, điểm
đến chuyến sau của một khách **độc lập thống kê** với mọi điểm đến họ đã đi.

Hệ quả, và đây là điểm quyết định cho G2:

- Trên dữ liệu đó, **bộ dự đoán tối ưu của điểm đến chuyến kế tiếp chính là độ phổ biến toàn cục.**
- Mọi dịch chuyển trọng số từ độ phổ biến sang sở thích **bắt buộc** làm temporal / nexttrip giảm, bất kể thuật toán tốt
  đến đâu.
- Và ngược lại: lợi ích của việc bám sở thích **không thể xuất hiện** ở hai split này.

Vậy −0,0381 không phải "chi phí thật của việc bám sở thích". Nó là hình phạt cho việc rời khỏi bộ dự đoán tối ưu **trên
dữ liệu mà sở thích được định nghĩa là nhiễu**. Hai split này không phải thước đo dùng được cho đánh đổi này.

### 2.3 Đo trên dữ liệu **có** sở thích

Bộ sinh khách giả lập (`theme_exp.make_user`) có sở thích thật (điểm đến mỗi chuyến đúng chủ đề với xác suất 80 %) và
**đã** ghi sẵn chuyến kế tiếp: `target` (khách sạn của chuyến sau) và `next` (điểm đến của chuyến sau). Thêm
`eval_profile --syn-target` để đo chúng. Kịch bản `between` (không có chuyến mở), 720 khách × 3 seed, CI ghép cặp:

| Cấu hình | tgtHit@20 (đúng **món** chuyến sau) | nextDestHit@20 (đúng **điểm đến** chuyến sau) | themePrec |
|---|---|---|---:|
| production (P0+F0) | 0.0000 | 0.4667 | 0.439 |
| P2+F0 | +0,0028 [+0,0000, +0,0069] | +0,0153 [+0,0000, +0,0319] | 0.431 |
| P2+F7 | +0,0111 [+0,0042, +0,0194] | **−0,2861** [−0,3208, −0,2472] | 0.762 |
| P2+F14c | +0,0125 [+0,0056, +0,0222] | **−0,2958** [−0,3306, −0,2583] | 0.769 |
| P2+F14 | +0,0125 [+0,0056, +0,0222] | **−0,3056** [−0,3417, −0,2653] | 0.785 |
| P2+F13a | +0,0125 [+0,0056, +0,0208] | **−0,3319** [−0,3667, −0,2931] | 0.782 |

Hai chiều trái ngược, cả hai đều có ý nghĩa thống kê:

1. **Mọi ứng viên thắng production ở việc đoán đúng món sẽ mua.** production hit **0,0 %** — không một lần nào trong 720
   khách; ứng viên đạt 1,1–1,25 %.
2. **Mọi ứng viên thua rất nặng ở độ phủ điểm đến.** Lý do: các món gần `u_long` nhất dồn vào ít điểm đến, còn production
   rải theo độ phổ biến nên phủ đúng các điểm đến lớn — mà `next` của bộ sinh cũng được bốc theo cỡ điểm đến *trong cùng
   chủ đề*.

**Kết luận cho G2:** lo ngại có cơ sở, nhưng cơ chế không phải "gợi ý sai gu" mà là **mất độ phủ điểm đến**. Đó là vấn đề
của bước *chọn danh sách*, không phải của trọng số — và vặn `W_POP` không sửa được (bảng quét pop ở report CI §3.4).

## 3. Giải pháp: giới hạn số món mỗi điểm đến khi không có chuyến mở

Giữ nguyên công thức F14c, thêm một giới hạn cứng "tối đa `cap` món mỗi điểm đến" vào bước MMR, **chỉ khi không có chuyến
mở** (`theme_study/dest_diversity.py`; có chuyến mở thì mọi món vốn cùng một điểm đến X nên giới hạn này sẽ phá nhánh đó).

### 3.1 Toàn bộ khách mỗi split + khách giả lập 3 seed

| Cấu hình | LLBO h@4 | temp h@20 | next h@20 | next h@4 | theme between | theme noisy_paired | nextDestHit@20 | tgtHit@20 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| production (P0+F0) | 0.5329 | 0.1587 | 0.0785 | 0.0256 | 0.439 | 0.376 | 0.4667 | 0.0000 |
| P2+F14c | 0.5324 | 0.1252 | 0.0403 | 0.0185 | 0.769 | 0.703 | 0.1708 | 0.0125 |
| P2+F14c + destCap1 | 0.5324 | 0.1226 | 0.0403 | 0.0185 | 0.717 | 0.670 | 0.5333 | 0.0125 |
| **P2+F14c + destCap2** | 0.5324 | **0.1277** | **0.0469** | **0.0202** | 0.756 | 0.698 | **0.4181** | 0.0111 |

### 3.2 CI ghép cặp

destCap2 **so với production**:

| Chỉ số | chênh | CI 95 % | G1 (0,04) |
|---|---:|---|---|
| LLBO h@20 / h@4 | +0,0000 / −0,0005 | [−0,0012, +0,0012] / [−0,0020, +0,0010] | ✅ |
| temporal h@20 | −0,0310 | [−0,0465, −0,0168] | ✅ đạt |
| nexttrip h@20 | −0,0316 | [−0,0409, −0,0218] | báo riêng (G2) |
| theme between | +0,3171 | [+0,2867, +0,3466] | ✅ |
| theme noisy_paired | +0,3220 | [+0,2888, +0,3528] | ✅ |
| `open` | +0,0000 | [0, 0], `nDiscordant = 0` | ✅ |
| tgtHit@20 (dữ liệu có sở thích) | +0,0111 / +0,0125 | [+0,0042, +0,0208] | — |
| nextDestHit@20 (dữ liệu có sở thích) | **−0,0486** | [−0,0889, −0,0056] | — |

destCap2 **so với P2+F14c** (cùng công thức, chỉ thêm giới hạn):

| Chỉ số | chênh | CI 95 % |
|---|---:|---|
| nextDestHit@20 `between` | **+0,2472** | [+0,2153, +0,2792] |
| nextDestHit@20 `noisy_paired` | **+0,1833** | [+0,1569, +0,2111] |
| nexttrip h@20 | +0,0065 | [+0,0000, +0,0136] — chưa phân biệt được |
| temporal h@20 | +0,0026 | [−0,0065, +0,0129] — chưa phân biệt được |
| theme between | −0,0130 | [−0,0185, −0,0071] |
| theme noisy_paired | −0,0054 | [−0,0088, −0,0024] |
| tgtHit@20 | −0,0014 / +0,0014 | CI chứa 0 |
| LLBO (cả ba chỉ số) | +0,0000 | [0, 0] |

**Điều quan trọng nhất:** giới hạn 2 món / điểm đến đưa khoảng cách độ phủ điểm đến so với production từ **−0,296 xuống
−0,049**, mà chỉ trả 0,013 theme. Trên split thật nó cũng kéo nexttrip h@20 từ 0,0403 lên 0,0469 và temporal từ 0,1252 lên
0,1277 — hai mức cải thiện này **chưa đạt ý nghĩa thống kê** (CI chạm 0), nên không được quảng cáo quá; mức cải thiện có
cơ sở vững là ở độ phủ điểm đến.

`destCap1` thì quá chặt: phủ điểm đến cao nhất (0,5333) nhưng theme tụt xuống 0,717 và không kéo được nexttrip.

## 4. Ô khám phá B trên tổ hợp đã chọn (G4)

`eval_slots.py --profile P2_confidence --scorer F14c_betweenQuantilePop35`, toàn bộ khách (LLBO 4.072 · temporal 775):

| Biến thể | LLBO h@4 | temporal h@4 | theme `open` | số món / list `open` | điểm đến khác / list `open` |
|---|---:|---:|---:|---:|---:|
| base (không có ô B) | 0.5324 | 0.1045 | 0.833 | 3.438 | 0.000 |
| **fillExplore (= ô B: chỉ lấp ô trống)** | **0.5324** | **0.1045** | 0.816 | 3.729 | **0.292** |
| explore1 (thay hẳn ô 4) | 0.4998 | 0.1019 | 0.817 | 3.729 | 1.000 |
| noSeen (ẩn món đã xem) | 0.3986 | 0.0297 | 0.833 | 3.438 | 0.000 |

- **Ô B miễn phí về độ chính xác:** hit@4 giống base đến bốn chữ số thập phân ở **cả hai** split. Nó chỉ lấp ô trống nên
  không đẩy món nào ra.
- Thêm món ở điểm đến khác cho **29,2 %** khách có chuyến mở; theme của list giảm 0,017 (món thêm vào ở điểm đến khác nên
  không tính vào cùng chủ đề).
- **Thay hẳn ô 4 thì mất 0,033 LLBO h@4** → giữ đúng luật "chỉ lấp ô trống", không thay món.
- **Ẩn món đã xem vẫn rất tệ** (LLBO h@4 0,5324 → 0,3986; 37,1 % target LLBO đã từng được xem) → giữ nguyên việc hiện lại
  món đã xem, đúng khuyến nghị 4 của báo cáo gốc.

Kết luận: G4 xác nhận được trên đúng tổ hợp P2 + F14c, không chỉ trên production + F0 như lượt 08/10 đầu.

**Đo lại theo đúng luật production (08/10, tối):** bảng trên xếp hạng món khám phá bằng `how="destsim"` (mặc định cũ của
`eval_slots.py`), còn engine sẽ xếp theo `cos(u_long, v)` qua `near_vector`. Chạy lại với cờ mới `--how ulong` (158 s,
`wp4_slots_p2_f14c_ulong.json`):

| Biến thể (`ulong`) | LLBO h@4 | temporal h@4 | theme `open` | số món / list `open` | điểm đến khác / list `open` |
|---|---:|---:|---:|---:|---:|
| base | 0.5324 | 0.1045 | 0.833 | 3.438 | 0.000 |
| **fillExplore** | **0.5324** | **0.1045** | 0.823 | 3.729 | **0.292** |
| explore1 | 0.4998 | 0.1019 | 0.817 | 3.729 | 1.000 |

Giống hệt `destsim` ở hit@4 và tỷ lệ thêm điểm đến; theme `open` 0,823 (so 0,816). Số trích trong đề xuất
`docs/prd/update/2026-10-08-recsys-o-kham-pha-khi-co-chuyen-mo.md` là bảng này.

## 5. Thời gian xếp hạng (WP4.3, một phần)

`theme_study/rank_latency.py`, split nexttrip (91 % khách không có chuyến mở — nhánh duy nhất bị đổi), k = 4, 400 khách,
3 lượt lặp lấy lượt nhanh nhất mỗi khách, máy không chạy job nào khác:

| Cấu hình | p50 | p95 | p99 | Δp95 so với production |
|---|---:|---:|---:|---:|
| production (P0+F0) | 29.62 ms | 38.63 ms | 40.09 ms | — |
| P2+F14c | 29.33 ms | 38.54 ms | 39.85 ms | **−0,09 ms** |
| P2+F14c + destCap2 | 29.51 ms | 39.26 ms | 40.14 ms | **+0,63 ms** |

**Đây không phải latency đầu-cuối của API.** Nó đo đúng phần bị đổi (dựng profile → chấm điểm → MMR) in-process trên vector
`.npy`; không gồm HTTP, auth, `near_vector` thật của Weaviate, đọc CDP. Tiêu chí G1 "p95 `/recommendations` không tăng quá
50 ms" vẫn cần đo bằng `recsys_bench http_latency` hoặc API local trước khi deploy. Số ở đây chỉ để trả lời: giới hạn theo
điểm đến làm vòng lặp MMR quét và loại nhiều ứng viên hơn, nhưng **không** làm bước xếp hạng đắt lên đáng kể (+0,63 ms p95).

## 6. Caveat khi trích dẫn

1. §2.3 và §3 dùng khách giả lập: nhãn chủ đề 58 điểm đến gán tay, điểm đến mỗi chuyến đúng chủ đề với xác suất 80 %, và
   `next` được bốc theo cỡ điểm đến trong cùng chủ đề — nên `nextDestHit` **vẫn** thưởng độ phổ biến, chỉ là trong phạm vi
   chủ đề. Đây là bộ đo tốt nhất đang có, không phải bộ đo đúng thực tế.
2. `tgtHit@20` ở mức 1,1–1,25 % là 8–9 khách trên 720; CI đã tính nhưng con số tuyệt đối nhỏ.
3. §2.2 là kết luận đọc code (`seed_histories.py`), không phải kết quả đo. Nó đúng với dữ liệu seed hiện tại; nếu bộ sinh
   event đổi (gate G6 / WP6) thì phải đọc lại.
4. `destCap` hiện chỉ là bản cài trong tiến trình đo (`dest_diversity.py` monkeypatch `mmr_select` và `_LocalSpace`).
   Muốn lên production thì phải cài trong `domain/recommendation/profile.py` (`mmr_select` nhận thêm mảng điểm đến) —
   chưa làm, chờ chốt.
5. Latency là ranking-only (xem §5).
6. Mọi số đo trên bản sao production 08/10 01:49, offline, chưa có A/B.

## 7. Lệnh tái sinh

Môi trường: report WP0 §6. Sau đó:

```bash
VEC=npy:/đường/dẫn/vectors/vec_prodcopy_e5s
AS_OF=2026-10-08T00:00:00+00:00
SYN="--n-syn 80 --scenarios between,open,noisy_paired --syn-seeds 42,7,2026 --syn-target"

# §2.3 dữ liệu có sở thích: production + F7, rồi F14c / F14 / F13a   (270 s, 200 s)
python -m src.evaluation.recsys_bench.theme_study.eval_profile --vec $VEC --as-of $AS_OF \
  --profiles P0_prod,P2_confidence --scorers F0_prod,F7_betweenMinmaxPop30 --splits "" $SYN \
  --per-user-out g2_a.jsonl --out g2_a.json
python -m src.evaluation.recsys_bench.theme_study.eval_profile --vec $VEC --as-of $AS_OF \
  --profiles P2_confidence --scorers F14c_betweenQuantilePop35,F14_betweenQuantilePop30,F13a_betweenCenter \
  --f14-cal-profile P2_confidence --splits "" $SYN --per-user-out g2_b.jsonl --out g2_b.json

# §3 giới hạn món / điểm đến, toàn bộ khách mỗi split   (477 s, 496 s)
for CAP in 1 2; do
  python -m src.evaluation.recsys_bench.theme_study.eval_profile --vec $VEC --as-of $AS_OF \
    --profiles P2_confidence --scorers F14c_betweenQuantilePop35 --f14-cal-profile P2_confidence \
    --max-users 0 $SYN --dest-cap $CAP --per-user-out dc$CAP.jsonl --out dc$CAP.json
done

# §2.1 ai mất hit, và target của họ có bán chạy không
python -m src.evaluation.recsys_bench.theme_study.loss_analysis --vec $VEC --as-of $AS_OF \
  --per-user p2_a.jsonl p4_c.jsonl --baseline P0_prod+F0_prod \
  --config P2_confidence+F14c_betweenQuantilePop35 --split nexttrip --metric hit@20 --out loss_nexttrip_hit20.json

# §4 ô khám phá B trên P2 + F14c
python -m src.evaluation.recsys_bench.theme_study.eval_slots --vec $VEC --as-of $AS_OF \
  --scorer F14c_betweenQuantilePop35 --profile P2_confidence --n-syn 80 --out slots_p2f14c.json
# cùng lệnh với --how ulong (xếp món khám phá theo cos(u_long, v) như production sẽ làm)
python -m src.evaluation.recsys_bench.theme_study.eval_slots --vec $VEC --as-of $AS_OF \
  --scorer F14c_betweenQuantilePop35 --profile P2_confidence --n-syn 80 --how ulong --out slots_p2f14c_ulong.json

# §5 thời gian xếp hạng (chạy khi máy không có job nào khác)
python -m src.evaluation.recsys_bench.theme_study.rank_latency --vec $VEC --as-of $AS_OF \
  --split nexttrip --k 4 --n-users 400 --repeat 3 \
  --arms "prod:P0_prod:F0_prod:0,f14c:P2_confidence:F14c_betweenQuantilePop35:0,f14c_destCap2:P2_confidence:F14c_betweenQuantilePop35:2" \
  --out latency.json

# CI
python -m src.evaluation.recsys_bench.theme_study.paired_ci --per-user g2_a.jsonl g2_b.jsonl dc1.jsonl dc2.jsonl \
  --baseline P0_prod+F0_prod --out ci_g2.json
```
