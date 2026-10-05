# Vòng đánh giá golden cho Itinerary Agent

Chi tiết runner, cờ và luật chấm: `docs/spec/agent/golden-run.md`. Cấu trúc case và khoá `expect`:
`docs/spec/agent/golden-dataset-how-to-add-more-case.md`. Dataset: `src/evaluation/datasets/agent_test_cases_nhat.yaml`
(lỗi người dùng tái hiện, có tiêu chí `judge` cho LLM giám khảo).

## Vòng làm việc

```
Eval loop:
- [ ] 1. Lỗi thật → case (câu chat nguyên văn, kỳ vọng chỉ ghi điều luôn đúng)
- [ ] 2. pytest src/evaluation/tests/test_golden.py
- [ ] 3. Baseline: case fail trên code cũ
- [ ] 4. Sửa code
- [ ] 5. Case pass (chạy 1 lần)
- [ ] 6. Cả bộ pass, biên bản vào src/evaluation/reports/
- [ ] 7. Đọc trace của mọi case fail trước khi kết luận
```

1. **Bắt đầu từ lỗi thật.** Chép câu chat từ trace hoặc báo lỗi, không tự nghĩ câu "đại diện". `id` dạng `TC-NN` theo
   `agent-test-cases-nhat.md`; không dùng lại id đã xoá.
2. **Kỳ vọng chỉ ghi điều luôn đúng** theo PRD và contract. Ví dụ `status: [COMPLETED, FALLBACK]` khi cả hai đều hợp lệ,
   không bắt đúng tên sản phẩm.
3. **Baseline trước khi sửa.** Case phải fail trên code cũ. Nếu nó pass thì case không bắt được lỗi.
4. **Chạy 1 lần.** Mặc định mỗi case chạy một lần. Chỉ thêm `--repeat N` khi một case lúc pass lúc fail và cần đo tỷ lệ;
   fail ngắt quãng là lỗi chập chờn ở bước LLM, xem trace của lần fail.
5. **Hai loại bộ.** Case mô tả năng lực mới có thể fail lúc đầu. Bộ hồi quy (case đã pass) phải giữ gần 100%, và mọi case
   fail trong bộ hồi quy chặn merge.
6. **Đọc transcript.** Số PASS/FAIL chỉ nói "có vấn đề". Trace LangSmith (`--trace-project <tên>`) mới nói vấn đề nằm ở node
   nào. Grader code (golden) rẻ và lặp lại được; khi cần chấm giọng văn thì thêm người đọc, không tự tin vào một LLM chấm điểm.
7. **Ghi đủ bối cảnh vào biên bản:** commit, model, data mode, số sản phẩm, latency p50/p95. Kết quả ở mode `fixture` chỉ
   chứng minh routing và grounding trên fixture, không chứng minh dữ liệu thật hay SLA.

## Mẫu case

```yaml
- id: TC-NN
  category: <nhóm ở mục 5 của tài liệu dataset>
  fr: [FR-AGT-03]
  turns:
    - message: <câu chat nguyên văn từ lỗi thật; ngày dùng {today+3}>
      expect:
        httpStatus: 200
        status: [COMPLETED, FALLBACK]
```

## Lệnh

```bash
.venv/bin/python -m pytest -q src/evaluation/tests/test_golden.py
.venv/bin/python -m src.evaluation.agent.golden --only TC-NN --trace-project <tên>
.venv/bin/python -m src.evaluation.agent.golden --sweep --trace-project <tên>
```

Cần Postgres đã seed và backend chạy với data mode thật (không phải `fixture`), và recsys đã nạp xong
(`startup.recsys.index.load.ready`). Xem `golden-run.md` mục chuẩn bị.
