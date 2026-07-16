"""RO automation package.

V135 introduces this package as the future home for RO case configuration,
feedwater, membrane, stage/pass, chemical, and report orchestration code.

Current state:
- `wave_ro_engine.py` is a compatibility facade.
- `wave_ro_engine_legacy.py` contains the previous full implementation.
- Later patches should move one behavior group at a time from legacy into this package.
"""
