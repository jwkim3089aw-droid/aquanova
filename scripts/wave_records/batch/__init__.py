"""Batch automation package.

V128 introduces this package as the future home for production-plan, resume,
artifact, retry, and runner code.

The existing implementation is intentionally preserved in
``wave_batch_legacy.py`` and re-exported through ``wave_batch.py`` first.
Later patches should move one behavior group at a time from legacy into this
package while keeping tests green.
"""
