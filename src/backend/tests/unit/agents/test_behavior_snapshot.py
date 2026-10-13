"""Lưới giữ hành vi khi refactor agent (`docs/plan/2026-10-11-refactor-agent-giu-hanh-vi.md`).

Phát lại mọi hội thoại của `behavior_snapshot/scenarios.json` qua graph với tool ghi từ chế độ `inprocess`
(`behavior_snapshot/tools.json.gz`) và LLM ghi sẵn (`behavior_snapshot/cassette.json`), rồi so từng lượt với
`behavior_snapshot/snapshot.json`: HTTP status, node đã đi, mã trần vòng/trần tool, response, lời gọi LLM và tool, state
đã lưu. Fail nghĩa là hành vi, payload gửi LLM hoặc tham số gọi tool đã đổi. Đổi có
chủ ý thì ghi lại bằng `behavior_snapshot.record` và đọc diff của snapshot trước khi commit.
"""
import unittest

from src.backend.tests.unit.agents.behavior_snapshot.harness import SNAPSHOT, load_json, replay


def first_difference(expected, actual, path="$"):
    """Đường dẫn và hai giá trị ở chỗ khác nhau đầu tiên, để đọc được ngay lượt nào đổi gì."""
    if type(expected) is not type(actual):
        return path, expected, actual
    if isinstance(expected, dict):
        for key in sorted(set(expected) | set(actual)):
            if key not in expected or key not in actual:
                return f"{path}.{key}", expected.get(key, "<thiếu>"), actual.get(key, "<thiếu>")
            found = first_difference(expected[key], actual[key], f"{path}.{key}")
            if found:
                return found
        return None
    if isinstance(expected, list):
        for index, (left, right) in enumerate(zip(expected, actual)):
            found = first_difference(left, right, f"{path}[{index}]")
            if found:
                return found
        if len(expected) != len(actual):
            return f"{path}.length", len(expected), len(actual)
        return None
    return None if expected == actual else (path, expected, actual)


class BehaviorSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.expected = load_json(SNAPSHOT, {})
        cls.actual = replay()

    def test_snapshot_covers_every_scenario(self):
        self.assertTrue(self.expected, "chưa có snapshot: chạy behavior_snapshot.record")
        self.assertEqual(sorted(self.expected), sorted(self.actual))

    def test_every_llm_payload_is_in_the_cassette(self):
        missing = [f"{name} lượt {index}" for name, turns in self.actual.items()
                   for index, turn in enumerate(turns, start=1) if turn["cassetteMiss"]]
        self.assertEqual(missing, [], "payload gửi LLM đã đổi ở các lượt này")

    def test_every_tool_call_is_in_the_cassette(self):
        missing = [f"{name} lượt {index}" for name, turns in self.actual.items()
                   for index, turn in enumerate(turns, start=1) if turn["toolMiss"]]
        self.assertEqual(missing, [], "tham số gọi tool đã đổi ở các lượt này")

    def test_each_turn_matches_the_recorded_behavior(self):
        for name, turns in self.expected.items():
            with self.subTest(scenario=name):
                found = first_difference(turns, self.actual.get(name))
                self.assertIsNone(found, f"{name}: {found}")


if __name__ == "__main__":
    unittest.main()
