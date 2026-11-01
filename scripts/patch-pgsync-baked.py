#!/usr/bin/env python3
"""
Patch PGSync 7.0.5 untuk test_decoding compatibility (PostgreSQL 15)
Baked-in ke base image — executed during docker build

Root Cause:
  PGSync 7.0.5 default: PLUGIN="test_decoding", options={"include-xids":"1"}
  pgoutput: binary protocol -> UnicodeDecodeError
  wal2json: JSON format -> parser regex mismatch -> LogicalSlotParseError

Solution:
  Keep PLUGIN="test_decoding" (text format, built-in PG15)
  Remove options dict (PG15 test_decoding doesn't need include-xids)
"""
from pathlib import Path

PGSYNC_DIR = Path("/usr/local/lib/python3.12/site-packages/pgsync")

# 1. Verify constants.py (should already be test_decoding)
constants = PGSYNC_DIR / "constants.py"
txt = constants.read_text()

# Force test_decoding if modified
if 'PLUGIN = "wal2json"' in txt or 'PLUGIN = "pgoutput"' in txt:
    txt = txt.replace('PLUGIN = "wal2json"', 'PLUGIN = "test_decoding"')
    txt = txt.replace('PLUGIN = "pgoutput"', 'PLUGIN = "test_decoding"')
    constants.write_text(txt)
    print("[OK] constants.py: PLUGIN -> test_decoding")
elif 'PLUGIN = "test_decoding"' in txt:
    print("[SKIP] constants.py: already test_decoding")
else:
    print("[WARN] constants.py: PLUGIN not found")

# 2. Patch sync.py: remove options dict
sync_py = PGSYNC_DIR / "sync.py"
txt = sync_py.read_text()

# Remove options line (include-xids causes error in PG15 test_decoding)
old = '''        cursor.start_replication(
            slot_name=self.__name,
            options={"include-xids": "1", "skip-empty-xacts": "1"},
            decode=True,  # gets you str instead of bytes
        )'''

new = '''        cursor.start_replication(
            slot_name=self.__name,
            decode=True,
        )'''

if old in txt:
    txt = txt.replace(old, new)
    print("[OK] sync.py: removed include-xids option")
else:
    print("[SKIP] sync.py: options already removed")

# Keep log message accurate
txt = txt.replace(
    'Starting logical replication stream (wal2json)...',
    'Starting logical replication stream (test_decoding)...'
)
txt = txt.replace(
    'Starting logical replication stream (pgoutput)...',
    'Starting logical replication stream (test_decoding)...'
)

sync_py.write_text(txt)
print("[OK] sync.py: log message updated")

# 3. Patch sync.py: skip logical messages (heartbeat, keepalive)
txt = sync_py.read_text()

# Find consume() method and add filter for logical messages
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
elif 'Skipping logical message' in txt:
    print("[SKIP] sync.py: consume() already patched")
else:
    print("[WARN] sync.py: consume() patch may need manual review")
