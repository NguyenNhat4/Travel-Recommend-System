"""Contract projection tests for the small catalog sample."""
import json
import tempfile
import unittest
from pathlib import Path

import make_sample


class MakeSampleTests(unittest.TestCase):
    def test_projects_price_unit_as_unknown_without_changing_catalog(self):
        row = {
            "productId": "00000000-0000-0000-0000-000000000001",
            "name": "Điểm tham quan mẫu",
            "taxonomy": "attraction",
            "destination": "Nha Trang",
            "description": "Mô tả đủ dài cho một điểm tham quan dùng trong bộ dữ liệu mẫu.",
            "attributes": {"latitude": 12.2, "longitude": 109.2},
            "unitPrice": 100000,
            "currency": "VND",
            "available": True,
            "availableFrom": None,
            "availableTo": None,
            "imageUrl": None,
            "sourceRef": "test:attraction:1",
        }
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            source = data / "products.jsonl"
            source.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
            before = source.read_bytes()
            make_sample.main(["--data-dir", str(data), "--per-variant", "1"])
            sample = json.loads((data / "sample" / "products-sample.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(sample["priceUnit"], "UNKNOWN")
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(set(row), set(sample) - {"priceUnit"})


if __name__ == "__main__":
    unittest.main()
