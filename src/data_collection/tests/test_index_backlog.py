import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

import httpx
import index_backlog as backlog


class BacklogTests(unittest.TestCase):
    def test_429_is_persisted_across_calls_then_success_clears_it(self):
        now = datetime(2026, 9, 30, tzinfo=timezone.utc)
        response = httpx.Response(429, headers={'Retry-After': '7200'}, request=httpx.Request('POST', 'https://api.cohere.com/v2/embed'))
        error = httpx.HTTPStatusError('quota', request=response.request, response=response)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'index.json'
            index = Mock(side_effect=error)
            result = backlog.guarded_index(path, index, now=now)
            self.assertTrue(result['deferred'])
            self.assertEqual(index.call_count, 1)
            blocked = Mock()
            self.assertTrue(backlog.guarded_index(path, blocked, now=now+timedelta(hours=1))['deferred'])
            blocked.assert_not_called()
            self.assertFalse(backlog.due(path, now+timedelta(hours=1)))
            self.assertTrue(backlog.due(path, now+timedelta(hours=2)))
            self.assertEqual(backlog.guarded_index(path, lambda: {'embedded': 7}, now=now+timedelta(hours=2)), {'embedded': 7})
            self.assertFalse(path.exists())

    def test_repeated_quota_expands_cooldown_but_other_errors_remain_fatal(self):
        now = datetime(2026, 9, 30, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'index.json'
            fn = Mock(side_effect=RuntimeError('Cohere 429'))
            backlog.guarded_index(path, fn, now=now)
            result = backlog.guarded_index(path, fn, now=now+timedelta(hours=1))
            self.assertEqual(result['rateLimitFailures'], 2)
            self.assertEqual(result['retryAfter'], (now+timedelta(hours=3)).isoformat())
            with self.assertRaisesRegex(RuntimeError, 'schema'):
                backlog.guarded_index(path, Mock(side_effect=RuntimeError('schema')), now=now+timedelta(hours=4))

    def test_wrapped_429_is_recognized(self):
        error = RuntimeError('index failed')
        error.__cause__ = RuntimeError('429 Too Many Requests')
        self.assertTrue(backlog.rate_limit(error)[0])
