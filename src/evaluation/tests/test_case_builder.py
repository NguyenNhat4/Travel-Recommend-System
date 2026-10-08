"""Unit test cho case_builder.py (tab "Thêm case" của eval_app.py). Không cần LLM/Postgres/backend."""

from datetime import date

import pytest

from src.evaluation.agent import case_builder as cb
from src.evaluation.agent.golden import EXPECT_KEYS, load_dataset

TODAY = date(2026, 10, 5)


def _case(**overrides):
    case = {
        "id": "TC-90", "category": "change_date", "fr": ["FR-AGT-01"],
        "turns": [
            {"message": "Đi Hà Nội 1 ngày từ {today+3}: 2 người", "expect": {
                "httpStatus": 200, "status": ["COMPLETED", "FALLBACK"],
                "intent": {"destination": "Hà Nội", "startDate": "{today+3:iso}", "party.adults": 2},
                "toolCalled": True, "forbiddenText": ["Lịch trình đã được hoàn tất"],
                "judge": ["Trợ lý nói rõ ngày đi.", "Nếu FALLBACK thì giải thích: vì sao"]}},
            {"message": "đổi khách sạn khác", "language": "en",
             "expect": {"excludeProductsFromTurn": {"turn": 1, "role": "stay"}}},
        ],
    }
    case.update(overrides)
    return case


@pytest.fixture()
def dataset(tmp_path):
    path = tmp_path / "cases.yaml"
    path.write_text(cb.DATASET_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    return path


def test_every_expect_key_of_the_runner_has_guidance():
    assert set(cb.FIELD_HELP) == EXPECT_KEYS
    grouped = [key for _, keys in cb.EXPECT_GROUPS for key in keys]
    assert sorted(grouped) == sorted(EXPECT_KEYS)


def test_generated_yaml_loads_back_through_the_runner(dataset):
    text = cb.case_to_yaml(_case(), "TC-90 — Đổi ngày.\nLỗi gốc: agent hỏi lại ngày.")
    assert text.startswith("# TC-90 — Đổi ngày.\n# Lỗi gốc")
    cb.append_case(text, dataset)
    loaded = {case.id: case for case in load_dataset(dataset)}["TC-90"]
    assert loaded.fr == ["FR-AGT-01"]
    assert loaded.turns[0].message == "Đi Hà Nội 1 ngày từ {today+3}: 2 người"
    assert loaded.turns[0].expect == _case()["turns"][0]["expect"]
    assert loaded.turns[1].language == "en"


def test_append_keeps_existing_content_byte_for_byte(dataset):
    before = dataset.read_text(encoding="utf-8")
    cb.append_case(cb.case_to_yaml(_case()), dataset)
    after = dataset.read_text(encoding="utf-8")
    assert after.startswith(before)
    assert after[len(before):].startswith("\n- id: TC-90")


def test_valid_case_passes_validation(dataset):
    errors, _ = cb.validate_block(cb.case_to_yaml(_case()), dataset, TODAY, ["Hà Nội"])
    assert errors == []


@pytest.mark.parametrize("change, message", [
    ({"id": "TC-01"}, "Trùng id"),
    ({"fr": []}, "FR/NFR"),
    ({"fr": ["AGT-1"]}, "sai định dạng"),
])
def test_case_level_errors_block_saving(dataset, change, message):
    errors, _ = cb.validate_block(cb.case_to_yaml(_case(**change)), dataset, TODAY)
    assert any(message in error for error in errors), errors


def test_turn_level_errors_block_saving(dataset):
    case = _case()
    case["turns"][0]["expect"]["status"] = ["DONE"]
    case["turns"][0]["expect"]["errorCode"] = "NOPE"
    case["turns"][0]["message"] = "đi {tomorrow}"
    case["turns"][0]["expect"]["intent"]["startDate"] = "{today+3:isoo}"
    case["turns"][1]["expect"]["excludeProductsFromTurn"]["turn"] = 2
    errors, _ = cb.validate_block(cb.case_to_yaml(case), dataset, TODAY)
    joined = "\n".join(errors)
    for expected in ("status 'DONE'", "errorCode 'NOPE'", "placeholder ngày", "excludeProductsFromTurn"):
        assert expected in joined


def test_unknown_expect_key_from_raw_yaml_is_rejected(dataset):
    text = "- id: TC-91\n  category: c\n  fr: [FR-AGT-01]\n  turns:\n    - message: a\n      expect: {missingField: [days]}\n"
    errors, _ = cb.validate_block(text, dataset, TODAY)
    assert any("missingField" in error for error in errors)


def test_unknown_destination_and_empty_expect_only_warn(dataset):
    case = _case()
    case["turns"][1]["expect"] = {}
    errors, warnings = cb.validate_block(cb.case_to_yaml(case), dataset, TODAY, ["Đà Nẵng"])
    assert errors == []
    assert any("Hà Nội" in w for w in warnings)
    assert any("lượt 2" in w and "chưa có kỳ vọng" in w for w in warnings)


def test_raw_yaml_must_be_exactly_one_case(dataset):
    errors, _ = cb.validate_block("id: TC-92\n", dataset, TODAY)
    assert errors and "đúng một case" in errors[0]


def test_next_case_id_follows_the_largest_tc_number():
    assert cb.next_case_id(["TC-01", "TC-10", "X-3"]) == "TC-11"
    assert cb.next_case_id([]) == "TC-01"


def test_option_lists_come_from_contract_and_code():
    assert "startDate" in cb.missing_field_values()
    assert "UNSUPPORTED_DESTINATION" in cb.error_codes()
    assert {"clarify", "tool", "narrate"} <= set(cb.node_names())
    assert "get_similar_products" in cb.tool_names()
    assert "FR-AGT-01" in cb.fr_codes()
