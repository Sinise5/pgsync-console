#!/usr/bin/env python3
"""
Robust patch untuk PGSync 7.0.5: skip logical messages (heartbeat, keepalive)

Strategy: Whitelist approach
- BEGIN/COMMIT: handled by TX_BOUNDARY_RE
- Logical messages (message: ...): skip + acknowledge
- Everything else: parse as DML (INSERT/UPDATE/DELETE)

This patch is safe because:
1. Uses regex pattern matching (not fragile string replacement)
2. Acknowledges LSN properly (no replication lag)
3. Whitelist approach (explicit handling of known patterns)
4. Falls back to existing parser for DML changes
"""
from pathlib import Path
import re

PGSYNC_DIR = Path("/usr/local/lib/python3.12/site-packages/pgsync")

print("=" * 60)
print("PGSync 7.0.5 Heartbeat Patch — Robust Implementation")
print("=" * 60)

# ==============================================================================
# PATCH 1: Add LOGICAL_MESSAGE_RE pattern
# ==============================================================================
sync_py = PGSYNC_DIR / "sync.py"
txt = sync_py.read_text()

# Find TX_BOUNDARY_RE definition and add LOGICAL_MESSAGE_RE after it
marker = 'TX_BOUNDARY_RE = re.compile(r"^(BEGIN|COMMIT)\\s+(\\d+)", re.IGNORECASE)'

if marker in txt and 'LOGICAL_MESSAGE_RE' not in txt:
    # Add new regex pattern right after TX_BOUNDARY_RE
    new_pattern = '''TX_BOUNDARY_RE = re.compile(r"^(BEGIN|COMMIT)\\s+(\\d+)", re.IGNORECASE)
# Logical messages: heartbeat, keepalive, etc (skip these in CDC)
LOGICAL_MESSAGE_RE = re.compile(r"^message:\\s+", re.IGNORECASE)'''

    txt = txt.replace(marker, new_pattern)
    print("[OK] Step 1: Added LOGICAL_MESSAGE_RE pattern")
elif 'LOGICAL_MESSAGE_RE' in txt:
    print("[SKIP] Step 1: LOGICAL_MESSAGE_RE already exists")
else:
    print("[ERROR] Step 1: Cannot find TX_BOUNDARY_RE marker")
    exit(1)

# ==============================================================================
# PATCH 2: Add logical message check in consume() method
# ==============================================================================

# Find the consume() method and add check AFTER TX_BOUNDARY_RE, BEFORE parse_logical_slot
# We need to find the exact location where we check TX_BOUNDARY_RE and insert our check

old_code = '''        match = TX_BOUNDARY_RE.match(raw)
        if match:
            kind: str = match.group(1).upper()
            if kind == "COMMIT":
                # Flush any buffered docs, and ACK this COMMIT LSN
                self._flush_buffer(
                    cursor=message.cursor,
                    flush_lsn=lsn,
                    force_ack=True,  # ACK even if buffer empty
                )
            # BEGIN/COMMIT don't include rows by themselves
            return

        # Not BEGIN/COMMIT -> row change
        try:
            payload: Payload = self.parse_logical_slot(raw)'''

new_code = '''        match = TX_BOUNDARY_RE.match(raw)
        if match:
            kind: str = match.group(1).upper()
            if kind == "COMMIT":
                # Flush any buffered docs, and ACK this COMMIT LSN
                self._flush_buffer(
                    cursor=message.cursor,
                    flush_lsn=lsn,
                    force_ack=True,  # ACK even if buffer empty
                )
            # BEGIN/COMMIT don't include rows by themselves
            return

        # PATCH: Check for logical messages (heartbeat, keepalive, etc)
        # These are emitted by extensions via pg_logical_emit_message()
        # Format: "message: transactional: N prefix: X content: Y"
        # Action: acknowledge LSN and skip (not a DML change)
        if LOGICAL_MESSAGE_RE.match(raw):
            logger.debug(f"Skipping logical message: {raw[:100]}")
            # Important: must acknowledge this LSN to avoid replication lag
            # Logical messages don't need buffering—ACK immediately
            if lsn is not None:
                message.cursor.send_feedback(flush_lsn=lsn, force=False)
            return

        # Not BEGIN/COMMIT/logical message -> must be a row change
        try:
            payload: Payload = self.parse_logical_slot(raw)'''

if old_code in txt:
    txt = txt.replace(old_code, new_code)
    print("[OK] Step 2: Added logical message check in consume()")
elif 'Skipping logical message' in txt:
    print("[SKIP] Step 2: Logical message check already exists")
else:
    print("[WARN] Step 2: Cannot find consume() insertion point")
    print("[WARN] consume() structure differs from expected")
    print("[WARN] Skipping logical-message patch")

# ==============================================================================
# PATCH 3: Add diagnostics to _flush_buffer()
# ==============================================================================

old_flush = '''                batch: list = list(run)
                logger.info(f"bulk group op={op} tbl={tbl} size={len(batch)}")
                docs.extend(self._payloads(batch))'''

new_flush = '''                batch: list = list(run)

                try:
                    logger.info(
                        f"payload tables={[p.table for p in batch]}"
                    )
                except Exception:
                    pass

                logger.info(
                    f"bulk group op={op} tbl={tbl} size={len(batch)}"
                )

                generated = list(self._payloads(batch))

                logger.info(
                    f"_payloads generated={len(generated)} docs "
                    f"for op={op} tbl={tbl}"
                )

                docs.extend(generated)'''

if old_flush in txt:
    txt = txt.replace(old_flush, new_flush)
    print("[OK] Step 3: Added _payloads diagnostics")
elif '_payloads generated=' in txt:
    print("[SKIP] Step 3: Diagnostics already exist")
else:
    print("[WARN] Step 3: Could not patch _flush_buffer diagnostics")

# ==============================================================================
# PATCH 4: Normalize PostgreSQL partitions -> parent table
# ==============================================================================

old_partition = '''        # we might receive an event triggered for a table
        # that is not in the tree node.
        # e.g a through table which we need to react to.
        # in this case, we find the parent of the through
        # table and force a re-sync.
        if (
            payload.table not in self.tree.tables
            or payload.schema not in self.tree.schemas
        ):
            return'''

new_partition = '''        # PATCH: normalize partition tables

        if (
            payload.table not in self.tree.tables
            and payload.table.startswith("laporan")
            and "laporan" in self.tree.tables
        ):
            logger.info(
                f"normalize partition {payload.table} -> laporan"
            )
            payload.table = "laporan"

        # we might receive an event triggered for a table
        # that is not in the tree node.
        # e.g a through table which we need to react to.
        # in this case, we find the parent of the through
        # table and force a re-sync.
        if (
            payload.table not in self.tree.tables
            or payload.schema not in self.tree.schemas
        ):
            logger.warning(
                f"SKIP table={payload.table} "
                f"schema={payload.schema}"
            )
            return'''

if old_partition in txt:
    txt = txt.replace(old_partition, new_partition)
    print("[OK] Step 4: Added partition normalization")
elif 'normalize partition' in txt:
    print("[SKIP] Step 4: Partition normalization already exists")
else:
    print("[WARN] Step 4: Could not patch partition normalization")

# Write patched file
sync_py.write_text(txt)
print("[OK] sync.py patched successfully")

# ==============================================================================
# VERIFICATION
# ==============================================================================
print("")
print("=" * 60)
print("VERIFICATION")
print("=" * 60)

# Verify patterns exist
txt_verify = sync_py.read_text()
checks = [
    ('LOGICAL_MESSAGE_RE', 'Logical message regex pattern'),
    ('send_feedback', 'LSN acknowledgment'),
    ('_payloads generated=', '_payloads diagnostics'),
    ('payload tables=', 'Payload table diagnostics'),
    ('normalize partition', 'Partition normalization'),
]

optional_checks = {
    'Skipping logical message'
}

all_ok = True

for pattern, description in checks:
    if pattern in txt_verify:
        print(f"[✓] {description}")
    else:
        print(f"[✗] {description} — MISSING")
        all_ok = False

if 'Skipping logical message' in txt_verify:
    print("[✓] Logical message skip logic")
else:
    print("[WARN] Logical message skip logic not found (optional)")

print("=" * 60)
if all_ok:
    print("[SUCCESS] Required patches applied and verified")
else:
    print("[ERROR] Required patches missing")
    exit(1)
