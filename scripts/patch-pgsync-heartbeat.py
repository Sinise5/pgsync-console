#!/usr/bin/env python3
"""
Patch PGSync 7.0.5 untuk skip logical messages (heartbeat, etc)
Baked-in ke base image — executed during docker build

Root Cause:
  test_decoding plugin emit 2 types:
  1. DML: table schema.table: INSERT/UPDATE/DELETE: ...
  2. Logical messages: message: transactional: 0/1 prefix: ... content: ...

  PGSync parser regex HANYA expect format #1 (table ...)
  Format #2 (message:) -> LogicalSlotParseError

Solution:
  Patch consume() untuk skip logical messages sebelum parser
"""
from pathlib import Path
import re

PGSYNC_DIR = Path("/usr/local/lib/python3.12/site-packages/pgsync")

# Patch sync.py: skip logical messages
sync_py = PGSYNC_DIR / "sync.py"
txt = sync_py.read_text()

# Find consume() method and add filter
old_consume = '''    def consume(self, message: t.Any) -> None:
        """
        Consume a single logical replication message.
        Parses the row, queues it in Redis, and sends feedback.
        """
        raw: str = message.payload.decode("utf-8")
        match = TX_BOUNDARY_RE.match(raw)'''

new_consume = '''    def consume(self, message: t.Any) -> None:
        """
        Consume a single logical replication message.
        Parses the row, queues it in Redis, and sends feedback.
        """
        raw: str = message.payload.decode("utf-8")

        # PATCH: Skip logical messages (heartbeat, keepalive, etc)
        # test_decoding can emit "message: transactional: N prefix: X content: Y"
        # PGSync parser only handles "table schema.table: OPERATION: ..."
        if raw.startswith("message:"):
            logger.debug(f"Skipping logical message: {raw[:80]}...")
            message.cursor.send_feedback(flush_lsn=message.data_start)
            return

        match = TX_BOUNDARY_RE.match(raw)'''

if old_consume in txt:
    txt = txt.replace(old_consume, new_consume)
    sync_py.write_text(txt)
    print("[OK] sync.py: patched consume() to skip logical messages")
else:
    print("[SKIP] sync.py: consume() already patched or different version")

# Verify patch
if 'Skipping logical message' in txt:
    print("[VERIFY] Patch applied successfully")
else:
    print("[WARN] Patch may not be applied correctly")
