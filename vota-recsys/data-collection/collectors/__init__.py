"""Collectors: one module per source, all behind the same contract.

The contract is spec section 8. Everything shared — robots, rate limiting,
retry, block detection, extraction helpers, the fetch/parse runners — lives in
``base.py``, ``net.py``, ``extract.py`` and ``runner.py``, so a collector module
is only the part that is genuinely site-specific: which URLs exist, and how to
read one.

Nothing is re-exported here on purpose: ``base.get_collector`` imports a source
module on demand, and a re-export in this file would make that a cycle.
"""
