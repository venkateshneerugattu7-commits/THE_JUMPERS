# Architecture Deep-Dive — ORIGIN

> **Software:** ORIGIN — BIP39/BIP32/BIP44/BIP49/BIP84 Wallet Toolkit  
> **Author:** Neerugattu Venkatesh  
> **Organization:** THE JUMPERS  
> **Version:** Pre-HORIZON (HORIZON: 01 AUG 2026)

---

## Table of Contents

1. [Design Philosophy](#design-philosophy)
2. [Single-File Architecture](#single-file-architecture)
3. [Cryptographic Stack](#cryptographic-stack)
4. [Memory & Performance](#memory--performance)
5. [Concurrency & File Locking](#concurrency--file-locking)
6. [Hunt Mode Design](#hunt-mode-design)
7. [Vault Persistence](#vault-persistence)
8. [UI Architecture](#ui-architecture)
9. [Error Handling Strategy](#error-handling-strategy)
10. [Security Model](#security-model)

---

## Design Philosophy

ORIGIN follows three core principles:

1. **Zero Dependencies** — The tool must work on any system with Python 3.8+, without `pip install`. Every cryptographic primitive is implemented from scratch.
2. **Verified Correctness** — All crypto is tested against official BIP test vectors on every startup. If any test fails, the program aborts.
3. **Production-Grade Resilience** — Long-running hunts must survive crashes, power failures, and concurrent access. Checkpoints, atomic writes, and file locking are non-negotiable.

---

## Single-File Architecture

### Rationale

The entire application lives in `ORIGIN.py` (~3000 lines). This is intentional:

| Concern | Single-File Solution |
|---------|---------------------|
| Distribution | One file to copy, no package management |
| Auditability | Entire codebase visible in one view |
| Dependency Hell | Zero external files required at runtime |
| Portability | Works on air-gapped systems |

### Trade-offs

- **Navigation:** Large file, but well-sectioned with `═` dividers
- **Testing:** All tests are inline (`run_tests()`)
- **Modularity:** Functions are grouped by feature, not by file

### Section Organization

```
1. STDLIB IMPORTS
2. OPTIONAL COINCURVE
3. ANSI TERMINAL COLOURS
4. HUNT UTILITIES (ETA, pause, logging)
5. BIP39 WORDLIST (2048 words)
6. SHA-256 (pure Python + hashlib)
7. RIPEMD-160 (pure Python + hashlib fallback)
8. HMAC-SHA-512 / PBKDF2
9. secp256k1 (pure Python + coincurve)
10. Base58Check / Bech32
11. BIP32 CKD / Address Derivation
12. BIP39 Helpers
13. COMBO GENERATORS
14. SELF-TESTS
15. VAULT (JSON + locking)
16. CHECKPOINT helpers
17. DISPLAY HELPERS
18. PROGRESS BAR
19. ADDRESS DATABASE (Bloom + mmap)
20. MODE 1 — COMBO GENERATOR
21. MODE 3 — MNEMONIC VERIFY
22. HUNT MODE — Combo scanner
23. MNEMONIC HUNT — Pattern scanner
24. MNEMONIC HUNT R — Permutation scanner
25. VAULT BROWSER
26. MAIN MENU
```

---

## Cryptographic Stack

### Layer 0: Primitives (from first principles)

```
SHA-256     → FIPS 180-4 block transform
RIPEMD-160  → ISO/IEC 10118-3 5-round compression
HMAC        → RFC 2104 ipad/opad construction
PBKDF2      → RFC 2898 iterative HMAC
secp256k1   → SECG curve parameters, point addition/doubling
Base58Check → Bitcoin alphabet, double-SHA256 checksum
Bech32      → BCH code over GF(32), 5-bit conversion
```

### Layer 1: BIP Standards

```
BIP39  → entropy_to_mnemonic / mnemonic_to_seed / validate_mnemonic
BIP32  → ckd_priv (child key derivation)
BIP44  → m/44'/0'/account'/change/index  → P2PKH  (1...)
BIP49  → m/49'/0'/account'/change/index  → P2SH-P2WPKH (3...)
BIP84  → m/84'/0'/account'/change/index  → P2WPKH (bc1q...)
```

### Layer 2: Application Logic

```
Combo Generator    → combos_asc/desc/exact → entropy → mnemonic → addresses
Hunt Mode          → combo → addresses → Bloom filter → set lookup
Mnemonic Hunt      → pattern → cand_lists → rank iteration → validation → addresses
Vault              → atomic JSON RMW with file locking
```

### Acceleration Path

```
Without coincurve:
  privkey_to_pubkey → _pt_mul (pure Python, ~50ms/op)

With coincurve:
  privkey_to_pubkey → coincurve.PrivateKey.format() (~0.5ms/op)
  Speedup: ~100x
```

The pure Python path is kept as fallback because:
1. `coincurve` requires a C compiler and OpenSSL headers
2. Some environments (embedded, restricted) cannot install compiled extensions
3. The fallback is verified correct against the same test vectors

---

## Memory & Performance

### Address Database

**Challenge:** Load millions of Bitcoin addresses into memory for O(1) lookup.

**Solution:** Two-tier structure:

```
Tier 1: Bloom Filter (probabilistic)
  - Size: ~1MB per 1M addresses (0.8% false positive rate)
  - Lookup: O(k) where k=7 hash functions
  - Use: Fast negative elimination (~1 microsecond)

Tier 2: Python set (exact)
  - Size: ~50 bytes per address
  - Lookup: O(1) average
  - Use: Confirm positives from Bloom filter
```

**Loading Strategy:**
```
1. mmap the file (avoids copying into Python heap)
2. Iterate line-by-line via mmap.readline()
3. Populate Bloom filter + set simultaneously
4. Report progress every 1M addresses
```

### secp256k1 Point Multiplication (Pure Python)

**Algorithm:** Double-and-add with Jacobian coordinates implicitly handled via affine formulas.

**Optimization:** Not optimized — correctness over speed. The `coincurve` path handles performance.

**Security Note:** Pure Python is NOT constant-time. Use `coincurve` for production.

### Memory Footprint

| Component | Memory |
|-----------|--------|
| WORDLIST | ~16 KB |
| SHA-256 constants | ~256 B |
| secp256k1 curve params | ~128 B |
| Bloom filter (1M addresses) | ~1 MB |
| Address set (1M addresses) | ~50 MB |
| Vault (typical) | <1 MB |
| **Total (1M addresses)** | **~52 MB** |

---

## Concurrency & File Locking

### Problem

Multiple processes may simultaneously:
- Read the vault (vault_browser)
- Write the vault (hunt auto-save, manual save)
- Read the address database (multiple hunt instances)

### Solution: Advisory File Locking

```python
# Unix: fcntl.flock — blocking, whole-file
fcntl.flock(f, fcntl.LOCK_EX)  # exclusive
fcntl.flock(f, fcntl.LOCK_SH)  # shared
fcntl.flock(f, fcntl.LOCK_UN)  # unlock

# Windows: msvcrt.locking — byte-range, non-blocking
# Workaround: retry loop with sleep
while True:
    try:
        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1<<30)
        break
    except OSError:
        time.sleep(0.25)
```

### Vault Write Protocol

```
1. Open file in 'a+' mode (create-if-missing, no truncate)
2. Acquire exclusive lock
3. Seek to 0, read entire content
4. Parse JSON
5. Check for duplicate mnemonic
6. Append new record
7. Seek to 0, truncate, write JSON
8. fsync() to disk
9. Release lock
```

### Atomic Save Protocol (vault_save)

```
1. Write to VAULT_FILE.tmp
2. fsync() tmp file
3. os.replace(VAULT_FILE.tmp, VAULT_FILE)  # atomic on POSIX
```

This ensures:
- Crash during write leaves original intact
- Readers never see partial JSON
- No lock needed for the replace operation (atomic)

---

## Hunt Mode Design

### Combo Hunt (Mode S)

**Flow:**
```
combo ranges → combos_asc/desc generator →
  bytes(v & 0xFF) → sha256 → entropy_to_mnemonic →
  mnemonic_to_seed → _derive_all_addresses →
  for each address: if address in AddressDB → MATCH
```

**Progress Tracking:**
- Total combos = product of (hi - lo + 1) for all ranges
- Progress bar: percentage + visual bar
- ETA: rolling 10-second window speed average

### Mnemonic Hunt (Mode M)

**Pattern Matching:**
```
User provides:
  - Word count (12/15/18/21/24)
  - Known words at specific positions
  - Candidate lists for unknown positions

System computes:
  - cand_lists: list of candidate indices per unknown slot
  - total_raw = product of len(cand_lists)
  - total_valid ≈ total_raw / 2^checksum_bits
```

**Rank-Based Iteration:**
```
for rank in range(start, stop):
  combo = index_to_combo(rank, cand_lists)
  fill unknown slots from combo
  if skip_dup and duplicates: continue
  if _validate_indices(pattern):
    derive addresses → check AddressDB
```

**Why Rank-Based?**
- Deterministic: rank N always produces the same mnemonic
- Resumable: checkpoint stores current rank
- Parallelizable: different processes can claim rank ranges
- Memory-efficient: no state needed between iterations

### Mnemonic Hunt R (Mode U) — Permutation

**Difference from Mode M:**
```
Mode M: Independent choice per slot (with replacement)
Mode R: Pool of candidates, draw without replacement
```

**Permutation Math:**
```
pool = union of all candidate lists (deduplicated)
n = len(pool)
k = number of unknown slots
total_raw = P(n, k) = n! / (n-k)!
```

**Slot Compatibility Check:**
```
perm = index_to_perm(rank, pool, k)
for each slot i: perm[i] must be in cand_sets[i]
```

This filters out permutations that don't satisfy the user's candidate constraints.

---

## Vault Persistence

### Record Schema

```json
{
  "timestamp": "2026-06-24T08:38:00",
  "combo": [4, 42, 5, 89, ...],
  "mnemonic": "abandon abandon ability ...",
  "seed_hex": "c55257c3...",
  "addresses": [
    {"type": "BIP84", "path": "m/84'/0'/0'/0/0", "address": "bc1q..."},
    {"type": "BIP49", "path": "m/49'/0'/0'/0/0", "address": "3..."},
    {"type": "BIP44", "path": "m/44'/0'/0'/0/0", "address": "1..."}
  ],
  "note": "HUNT MATCH: bc1q..."
}
```

### Vault Browser Features

| Feature | Implementation |
|---------|---------------|
| Browse | Paginated (5 records/page) |
| Search Address | Substring match across all addresses |
| Search Keyword | Substring match in mnemonic, note, or combo |
| Delete | Pop by index, atomic save |
| Export CSV | Flatten addresses to rows |
| Export TXT | Human-readable with formatting |
| Add Note | In-place edit, atomic save |

---

## UI Architecture

### Terminal UI Design

**Constraints:**
- Must work over SSH
- Must work in Docker containers
- Must work without curses/ncurses (zero dependencies)
- Must support Windows CMD and PowerShell

**Solution:** ANSI escape codes with TTY detection

```python
_USE_COLOR = sys.stdout.isatty()
def _c(code): return f"[{code}m" if _USE_COLOR else ""
```

When not a TTY (piped, redirected, CI), all codes return empty strings.

### Box Drawing Characters

Uses Unicode box-drawing for headers:
```
╔══════════════════════════════════════════════════════════════════════════╗
║          BIP39 / BIP32 / BIP44 / BIP49 / BIP84  WALLET TOOLKIT         ║
╚══════════════════════════════════════════════════════════════════════════╝
```

### Navigation Model

```
_HomeSignal(Exception)
  └── Raised anywhere in the call stack
  └── Caught at main_menu() loop boundary
  └── Redraws main menu
```

This allows instant "Home" navigation from any depth without nested return statements.

### Input Handling

```python
def prompt(msg, default=None):
    v = input(f"» {msg}: ").strip()
    if v.upper() == "H":
        raise _HomeSignal
    return v if v else default
```

All prompts support `H` → home menu. EOFError and KeyboardInterrupt are caught gracefully.

---

## Error Handling Strategy

### Philosophy

1. **Crypto errors are fatal** — abort on any mismatch
2. **User input errors are recoverable** — re-prompt with explanation
3. **File errors are logged** — continue if possible (hunt_log.txt)
4. **KeyboardInterrupt is graceful** — save checkpoint, clean exit

### Hierarchy

```
FATAL (sys.exit):
  └── run_tests() failure on startup
  └── Any crypto primitive producing wrong output

RECOVERABLE (warn + continue):
  └── Invalid user input (re-prompt)
  └── File not found (explain + return to menu)
  └── Vault parse error (return empty list)

GRACEFUL (save state + exit):
  └── KeyboardInterrupt in hunt mode
  └── _HomeSignal anywhere

SILENT (ignore):
  └── hunt_log write failure
  └── Checkpoint save failure
```

---

## Security Model

### Threat Model

| Threat | Mitigation |
|--------|-----------|
| Supply chain attack | Single file, auditable, no pip deps |
| Crypto implementation bug | Self-tests on every startup |
| Memory dump | Keys exist only during derivation; not stored |
| Vault theft | Plaintext JSON — protect at OS level |
| Timing attack on secp256k1 | Use `coincurve` for constant-time ops |
| Side-channel (power analysis) | Not mitigated — use in isolated environment |
| Weak entropy | User provides combos/patterns — deterministic by design |

### Design Decisions

1. **No OS randomness** — ORIGIN is deterministic by design. The user provides the search space (combos or patterns). This is intentional for wallet recovery scenarios.

2. **Plaintext vault** — Encryption would add dependencies and key management complexity. Users are expected to protect the file via OS permissions.

3. **No network calls** — The tool never connects to the internet. Address databases must be provided offline.

4. **Self-test on startup** — Not optional. If vectors fail, the tool refuses to run. This prevents silent corruption.

5. **Pure Python fallback** — Even if `coincurve` is compromised, the pure Python path is verified independently.

---

*End of Architecture Deep-Dive*
