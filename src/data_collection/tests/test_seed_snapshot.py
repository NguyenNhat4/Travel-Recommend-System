import gzip
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from data_collection.seed.snapshot import materialize_snapshot


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SnapshotTests(unittest.TestCase):
    def make_snapshot(self, root: Path) -> Path:
        source = root / "products.jsonl"
        source.write_text('{"productId":"one"}\n{"productId":"two"}\n', encoding="utf-8")
        archive = root / "products.jsonl.gz"
        with source.open("rb") as raw, archive.open("wb") as output:
            with gzip.GzipFile(fileobj=output, mode="wb", mtime=0) as compressed:
                compressed.write(raw.read())
        manual = root / "combo_items_manual.jsonl"
        manual.write_text('{"combo_product_id":"one"}\n', encoding="utf-8")
        manifest = {
            "schemaVersion": 1,
            "snapshotId": "test-snapshot",
            "products": {
                "file": archive.name,
                "rows": 2,
                "sha256": sha256(source),
                "gzipSha256": sha256(archive),
            },
            "comboManual": {
                "file": manual.name,
                "rows": 1,
                "sha256": sha256(manual),
            },
        }
        (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return archive

    def test_materializes_verified_products_and_manual_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = self.make_snapshot(root)
            runtime = root / "runtime"

            products = materialize_snapshot(archive, runtime)

            self.assertEqual(products.read_text(encoding="utf-8").count("\n"), 2)
            self.assertEqual(products.parent.name, "test-snapshot")
            self.assertTrue((products.parent / "combo_items_manual.jsonl").is_file())
            self.assertTrue(archive.is_file())

    def test_rejects_changed_archive_before_materializing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = self.make_snapshot(root)
            archive.write_bytes(archive.read_bytes() + b"changed")

            with self.assertRaisesRegex(ValueError, "compressed checksum mismatch"):
                materialize_snapshot(archive, root / "runtime")
            self.assertFalse((root / "runtime").exists())


if __name__ == "__main__":
    unittest.main()
