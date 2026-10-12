import unittest
from datetime import date
from unittest.mock import Mock, patch

from data_collection.seed import demo_data


class _Conn:
    def __init__(self, has_column):
        self.has_column = has_column

    def execute(self, sql, params=None):
        value = (1 if self.has_column else 0) if "information_schema" in sql else date(2026, 10, 9)
        return Mock(fetchone=lambda: (value,))


class DemoDataTests(unittest.TestCase):
    def run_sync(self, has_column, as_of=None):
        calls = Mock()
        rooms = Mock(return_value={'simulatedRooms': 2})
        fill = Mock(side_effect=[{'fillWritten': 5, 'fillOneWay': 1}, {'fillWritten': 3, 'fillOneWay': 2}])
        combos = Mock(return_value={'comboItems': 4})
        calls.attach_mock(rooms, 'rooms'), calls.attach_mock(fill, 'fill'), calls.attach_mock(combos, 'combos')
        conn = _Conn(has_column)
        with patch('data_collection.seed.simulated_rooms.sync', rooms), patch('data_collection.seed.simulated_fill.sync', fill), \
                patch('data_collection.seed.combo_components.sync', combos):
            counts = demo_data.sync(conn, as_of)
        return counts, [c[0] for c in calls.mock_calls], fill

    def test_runs_rooms_fill_combos_fill_in_order(self):
        counts, order, fill = self.run_sync(True, date(2026, 10, 10))
        self.assertEqual(order, ['rooms', 'fill', 'combos', 'fill'])
        self.assertEqual(counts, {'simulatedRooms': 2, 'comboItems': 4, 'fillWritten': 8, 'fillOneWay': 2})
        self.assertEqual(fill.call_args.kwargs['as_of'], date(2026, 10, 10))

    def test_as_of_is_inferred_from_room_window(self):
        _, _, fill = self.run_sync(True)
        self.assertEqual(fill.call_args.kwargs['as_of'], date(2026, 10, 9))

    def test_without_migration_0010_combo_step_is_skipped(self):
        with self.assertLogs('data_collection.seed.demo_data', 'WARNING'):
            counts, order, _ = self.run_sync(False, date(2026, 10, 10))
        self.assertEqual(order, ['rooms', 'fill', 'fill'])
        self.assertEqual(counts['comboComponentsSkipped'], 1)


if __name__ == '__main__':
    unittest.main()
