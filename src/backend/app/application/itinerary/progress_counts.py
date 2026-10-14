"""Request-local accounting at the existing filters; never changes a filter decision."""
from collections import Counter


class ProductCounts:
    def __init__(self):
        self.rows = {}
        self.source_total = None
        self.source_more = False

    def record(self, product_id, reason=None, *, outside=False):
        if product_id:
            self.rows[product_id] = (reason, outside)

    def snapshot(self, chosen=None):
        outside = Counter(reason for reason, out in self.rows.values() if out and reason)
        dropped = Counter(reason for reason, out in self.rows.values() if not out and reason)
        eligible = {pid for pid, (reason, out) in self.rows.items() if not reason and not out}
        result = dict(received=len(self.rows), inScope=len(self.rows)-sum(outside.values()),
                      eligible=len(eligible), outOfScope=dict(outside), dropped=dict(dropped),
                      sourceMore=self.source_more)
        if self.source_total is not None:
            result['sourceTotal'] = self.source_total
        if chosen is not None:
            result['chosen'] = len(eligible & chosen)
        return result
