import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import daily
from seed.snapshot import materialize_snapshot


def row(pid, src="agoda", available=True, price=100, **attrs):
    return {"productId": pid, "name": f"SP {pid}", "taxonomy": "hotel", "destination": "Nha Trang", "sourceRef": f"{src}:hotel:{pid}",
            "available": available, "unitPrice": price, "description": "mô tả", "imageUrl": "https://x/y.jpg",
            "attributes": {"latitude": 12.2, "longitude": 109.2, **attrs}}


class CarryForwardTest(unittest.TestCase):
    def test_keeps_unseen_rows_and_retires_after_seven_days(self):
        previous = [row("a"), row("b"), row("c")]
        ledger = {"b": "2026-09-16", "c": "2026-09-20"}
        catalog, new_ledger, stats = daily.carry_forward([row("a"), row("d")], previous, ledger, date(2026, 9, 23))
        by_id = {r["productId"]: r for r in catalog}
        self.assertEqual(set(by_id), {"a", "b", "c", "d"})  # catalog chỉ tăng
        self.assertFalse(by_id["b"]["available"])            # 7 ngày không thấy → ngừng bán
        self.assertTrue(by_id["c"]["available"])             # 3 ngày: vẫn bán
        self.assertEqual(by_id["b"]["attributes"]["lastSeenAt"], "2026-09-16")
        self.assertEqual((stats["new"], stats["carried"], stats["retired"]), (1, 1, 1))
        self.assertEqual(new_ledger["a"], "2026-09-23")
        self.assertNotIn("lastSeenAt", previous[1]["attributes"])  # không sửa đầu vào

    def test_first_run_without_ledger_starts_counting_today(self):
        catalog, ledger, _ = daily.carry_forward([], [row("x")], {}, date(2026, 9, 23))
        self.assertTrue(catalog[0]["available"])
        self.assertEqual(ledger["x"], "2026-09-23")


class GateTest(unittest.TestCase):
    def test_blocks_count_drop_coverage_drop_and_shrinking(self):
        old = daily.profile([row(str(i)) for i in range(10)])
        dropped = daily.profile([row(str(i), available=i < 7) for i in range(10)])
        self.assertTrue(any("đang bán giảm" in p for p in daily.gate(dropped, old)))
        no_price = daily.profile([row(str(i), price=None if i < 5 else 100) for i in range(10)])
        self.assertTrue(any("unitPrice" in p for p in daily.gate(no_price, old)))
        shrunk = daily.profile([row(str(i)) for i in range(9)])
        self.assertTrue(any("catalog chỉ được tăng" in p for p in daily.gate(shrunk, old)))
        self.assertEqual(daily.gate(daily.profile([row(str(i)) for i in range(12)]), old), [])


class DiffTest(unittest.TestCase):
    def test_kinds(self):
        old = [row("a"), row("b"), row("c", price=100), row("d", available=False), row("e")]
        new = [row("a"), row("b", available=False), row("c", price=120), row("d"), row("f"), row("e", images=["n"])]
        d = daily.diff_versions(old, new)
        self.assertEqual({k: v["count"] for k, v in d.items()},
                         {"added": 1, "removed": 0, "retired": 1, "revived": 1, "priceChanged": 1, "otherChanged": 1})
        self.assertEqual(d["priceChanged"]["sample"][0]["oldUnitPrice"], 100)


class VersionLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name) / "data"
        (self.data / "state").mkdir(parents=True)
        (self.data / "combo_items_manual.jsonl").write_text('{"combo_product_id": "c", "position": 1}\n', encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def publish(self, rows):
        daily.write_rows(self.data / "products.jsonl", rows)
        return daily.create_version(self.data, "run", {"new": 0}, today=date(2026, 9, 23))

    def test_create_switch_freeze(self):
        v1 = self.publish([row("a"), row("b")])
        v2 = self.publish([row("a"), row("b", price=150), row("c")])
        self.assertEqual((v1, v2), ("2026-09-23", "2026-09-23.2"))
        self.assertEqual(daily.active_version(self.data), v2)
        self.assertEqual([m["version"] for m in daily.list_versions(self.data)], [v2, v1])
        self.assertEqual(daily.read_manifest(self.data, v2)["available"], 3)

        info = daily.switch_version(self.data, v1)
        self.assertEqual((info["previous"], daily.active_version(self.data)), (v2, v1))
        self.assertEqual([r["productId"] for r in daily.read_rows(self.data / "products.jsonl")], ["a", "b"])
        self.assertTrue(list((self.data / "backups").glob("products-switch-*.jsonl.gz")))

        snapshots = Path(self.tmp.name) / "snapshots"
        target = daily.freeze_version(self.data, v1, "v1", snapshots=snapshots)
        self.assertEqual(json.loads((target / "manifest.json").read_text(encoding="utf-8"))["release"], "v1")
        # snapshot đóng băng phải qua được đúng bước kiểm tra checksum của seed
        runtime = materialize_snapshot(target / "products.jsonl.gz", Path(self.tmp.name) / "runtime")
        self.assertEqual(len(daily.read_rows(runtime)), 2)
        with self.assertRaises(ValueError):
            daily.freeze_version(self.data, v2, "v1", snapshots=snapshots)  # nhãn đã dùng
        with self.assertRaises(ValueError):
            daily.freeze_version(self.data, v1, "v1-lai", snapshots=snapshots)  # snapshot không được ghi đè

    def test_same_content_gives_same_gzip(self):
        a = self.publish([row("a")])
        b = self.publish([row("a")])
        self.assertEqual(daily.read_manifest(self.data, a)["products"]["gzipSha256"],
                         daily.read_manifest(self.data, b)["products"]["gzipSha256"])

    def test_rejects_bad_version_ids(self):
        for bad in ("../x", "2026-09-23/../../etc", "latest"):
            with self.assertRaises(ValueError):
                daily.read_manifest(self.data, bad)

    def test_prune_keeps_labeled_and_active(self):
        versions = [self.publish([row(str(i))]) for i in range(4)]
        manifest = daily.read_manifest(self.data, versions[0])
        manifest["label"] = "v1"
        daily.write_manifest(self.data, manifest)
        daily.prune_versions(self.data, keep=1)
        left = {m["version"] for m in daily.list_versions(self.data)}
        self.assertEqual(left, {versions[0], versions[-1]})


class TargetEnvTest(unittest.TestCase):
    def test_missing_vars_are_named_and_weaviate_gets_scheme(self):
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {"CLOUD_SEED_DATABASE_URL": "", "CLOUD_WEAVIATE_URL": "abc.weaviate.cloud"}, clear=False):
            env, missing = daily.target_env("cloud")
        self.assertEqual(missing, ["CLOUD_SEED_DATABASE_URL"])
        self.assertEqual(env["WEAVIATE_URL"], "https://abc.weaviate.cloud")

    def test_cloud_reuses_backend_key_only_for_same_cluster(self):
        import os
        from unittest import mock
        same = {"CLOUD_WEAVIATE_URL": "https://abc.weaviate.cloud", "CLOUD_WEAVIATE_API_KEY": "", "WEAVIATE_URL": "abc.weaviate.cloud",
                "WEAVIATE_API_KEY": "k1"}
        with mock.patch.dict(os.environ, same, clear=False):
            self.assertEqual(daily.target_env("cloud")[0]["WEAVIATE_API_KEY"], "k1")
        with mock.patch.dict(os.environ, {**same, "WEAVIATE_URL": "http://localhost:8080"}, clear=False):
            self.assertEqual(daily.target_env("cloud")[0]["WEAVIATE_API_KEY"], "")

    def test_empty_line_does_not_shadow_later_file(self):
        import os
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DAILY_TEST_VAR", None)
            a, b = Path(tmp) / "a.env", Path(tmp) / "b.env"
            a.write_text("DAILY_TEST_VAR=\n", encoding="utf-8")
            b.write_text("DAILY_TEST_VAR='co gia tri'\n", encoding="utf-8")
            daily.load_env((a, b))
            self.assertEqual(os.environ["DAILY_TEST_VAR"], "co gia tri")



@unittest.skipUnless(__import__("os").environ.get("CATALOG_ONLY_TEST_DATABASE_URL"),
                     "cần CATALOG_ONLY_TEST_DATABASE_URL: database vota dùng một lần, đã có schema db/init")
class UpsertCatalogIntegrationTest(unittest.TestCase):
    """CHỈ trỏ vào database dùng một lần: test để lại 2 sản phẩm test-daily-* và bước retire_missing chuyển MỌI dòng khác của
    cdp.products sang available=false (đúng hành vi khi switch sang một catalog chỉ có 1 dòng)."""

    def test_upsert_is_idempotent_and_retire_missing_never_deletes(self):
        import os
        import uuid

        import psycopg

        from seed.database import upsert_catalog
        url = os.environ["CATALOG_ONLY_TEST_DATABASE_URL"]
        tag = uuid.uuid4().hex[:8]
        ids = [str(uuid.uuid4()), str(uuid.uuid4())]

        def product(pid, name, price):
            return {"product_id": pid, "name": name, "taxonomy": "attraction", "destination": "Nha Trang", "description": "test",
                    "attributes": {}, "unit_price": price, "currency": "VND", "available": True, "available_from": None,
                    "available_to": None, "image_url": None, "source_ref": f"test-daily-{tag}:{name}"}

        with tempfile.TemporaryDirectory() as tmp:
            loader = Path(tmp) / "loader"
            loader.mkdir()

            def load(rows, **kw):
                (loader / "cdp_products.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
                return upsert_catalog(url, Path(tmp), **kw)

            first = load([product(ids[0], "a", 100), product(ids[1], "b", 200)])
            self.assertEqual((first["cdp.products inserted"], first["cdp.products updated"]), (2, 0))
            again = load([product(ids[0], "a", 100), product(ids[1], "b", 200)])
            self.assertEqual((again["cdp.products inserted"], again["cdp.products updated"]), (0, 0))
            changed = load([product(ids[0], "a", 150), product(ids[1], "b", 200)])
            self.assertEqual(changed["cdp.products updated"], 1)
            with psycopg.connect(url) as conn:
                before = conn.execute("SELECT count(*) FROM cdp.products").fetchone()[0]
            retired = load([product(ids[0], "a", 150)], retire_missing=True)
            self.assertGreaterEqual(retired["cdp.products not in catalog → available=false"], 1)
            with psycopg.connect(url) as conn:
                self.assertEqual(conn.execute("SELECT count(*) FROM cdp.products").fetchone()[0], before)  # không xoá dòng nào
                self.assertFalse(conn.execute("SELECT available FROM cdp.products WHERE product_id = %s", (ids[1],)).fetchone()[0])


if __name__ == "__main__":
    unittest.main()


class IndexQuotaTest(unittest.TestCase):
    def test_quota_pending_keeps_load_success_and_continues_next_target(self):
        with tempfile.TemporaryDirectory() as d:
            run = daily.Run(Path(d), 'quota-test')
            (run.data / 'state').mkdir(exist_ok=True)
            (run.data / 'state/index_pending-cloud.json').write_text(json.dumps({'pending': True}))
            env = {'WEAVIATE_URL': 'https://example.com', 'COHERE_API_KEY': 'test'}
            with patch.object(daily, 'target_env', return_value=(env, [])), \
                    patch.object(daily.subprocess, 'call', return_value=0) as call, \
                    patch.object(daily, 'record_loaded') as recorded:
                self.assertTrue(daily.load_targets(run, ['cloud', 'local'], True, date(2026, 9, 30)))
            self.assertEqual(call.call_count, 4)
            self.assertEqual(recorded.call_count, 2)
            self.assertEqual(run.state['load']['cloud']['status'], 'partial')
            self.assertEqual(run.state['load']['local']['status'], 'ok')


class IndexGateTest(unittest.TestCase):
    """Bước embed sau khi nạp: EMBED_PROVIDER=local (mặc định) không cần key, cohere (đường lui) bắt buộc COHERE_API_KEY."""

    def test_local_provider_needs_only_weaviate(self):
        self.assertEqual(daily.index_missing({'WEAVIATE_URL': 'https://w'}), [])
        self.assertEqual(daily.index_missing({'WEAVIATE_URL': 'https://w', 'EMBED_PROVIDER': 'local'}), [])
        self.assertEqual(daily.index_missing({'WEAVIATE_URL': 'https://w', 'EMBED_PROVIDER': ''}), [])
        self.assertEqual(daily.index_missing({}), ['WEAVIATE_URL'])

    def test_cohere_rollback_requires_the_key(self):
        self.assertEqual(daily.index_missing({'WEAVIATE_URL': 'https://w', 'EMBED_PROVIDER': ' Cohere '}),
                         ['COHERE_API_KEY'])
        self.assertEqual(daily.index_missing({'EMBED_PROVIDER': 'cohere'}), ['WEAVIATE_URL', 'COHERE_API_KEY'])
        self.assertEqual(daily.index_missing({'WEAVIATE_URL': 'https://w', 'EMBED_PROVIDER': 'cohere',
                                              'COHERE_API_KEY': 'k'}), [])

    def load(self, env):
        with tempfile.TemporaryDirectory() as d:
            run = daily.Run(Path(d), 'gate-test')
            with patch.object(daily, 'target_env', return_value=(env, [])), \
                    patch.object(daily.subprocess, 'call', return_value=0) as call, \
                    patch.object(daily, 'record_loaded'):
                ok = daily.load_targets(run, ['local'], True, date(2026, 10, 6))
            return ok, call, run.state['load']['local']

    def test_load_runs_the_index_without_cohere_key_on_local_provider(self):
        ok, call, res = self.load({'WEAVIATE_URL': 'http://localhost:8080', 'EMBED_PROVIDER': 'local'})
        self.assertTrue(ok)
        self.assertEqual(call.call_count, 2)  # seed + index_backlog
        self.assertIn('src.data_collection.index_backlog', call.call_args_list[1].args[0])
        self.assertNotIn('index', res)

    def test_load_skips_the_index_when_cohere_has_no_key(self):
        ok, call, res = self.load({'WEAVIATE_URL': 'http://localhost:8080', 'EMBED_PROVIDER': 'cohere'})
        self.assertTrue(ok)
        self.assertEqual(call.call_count, 1)  # chỉ seed
        self.assertEqual(res['index'], 'skipped: thiếu COHERE_API_KEY')


class CrawlerImageEmbeddingTest(unittest.TestCase):
    """Image job index (daily, fresh-catalog) có đúng model/revision mà image backend dùng để tra (cùng không gian)."""

    def test_crawler_images_pin_the_backend_model_and_cpu_torch(self):
        import re
        backend_file = (daily.REPO_ROOT / 'Dockerfile.backend').read_text(encoding='utf-8')
        for name in ('Dockerfile.daily', 'Dockerfile.fresh-catalog'):
            image = (daily.REPO_ROOT / name).read_text(encoding='utf-8')
            with self.subTest(image=name):
                for arg in ('EMBED_MODEL', 'EMBED_MODEL_REVISION'):
                    pattern = rf'^ARG {arg}=(\S+)'
                    self.assertEqual(re.search(pattern, image, re.M).group(1),
                                     re.search(pattern, backend_file, re.M).group(1))
                self.assertIn('--index-url https://download.pytorch.org/whl/cpu', image)
                self.assertIn('-r /tmp/backend-requirements-embed.txt', image)
                self.assertIn('HF_HUB_OFFLINE=1', image)
                self.assertIn('.warmup()', image)
