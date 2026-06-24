# Developer Guide — ORIGIN

> **Software:** ORIGIN — BIP39/BIP32/BIP44/BIP49/BIP84 Wallet Toolkit  
> **Author:** Neerugattu Venkatesh  
> **Organization:** THE JUMPERS  
> **Version:** Pre-HORIZON (HORIZON: 01 AUG 2026)

---

## Table of Contents

1. [Development Environment](#development-environment)
2. [Code Structure](#code-structure)
3. [Adding a New Feature](#adding-a-new-feature)
4. [Cryptographic Changes](#cryptographic-changes)
5. [Testing](#testing)
6. [Performance Optimization](#performance-optimization)
7. [Debugging](#debugging)
8. [Release Process](#release-process)

---

## Development Environment

### Setup

```bash
# Clone
git clone https://github.com/THEJUMPERS/ORIGIN.git
cd ORIGIN

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dev dependencies
pip install coincurve pytest

# Verify
python3 ORIGIN.py
# Select [T] to run self-tests
```

### Recommended Tools

| Tool | Purpose |
|------|---------|
| `pytest` | Test runner |
| `black` | Code formatter (line length: 100) |
| `flake8` | Linter |
| `mypy` | Type checking |

---

## Code Structure

### Section Map

```
Lines    Section
─────────────────────────────────────────
1-50     Shebang, docstring, imports
50-100   Optional coincurve detection
100-200  ANSI color definitions
200-350  UI helpers (prompt, spin, etc.)
350-500  Hunt utilities (ETA, pause, log)
500-750  BIP39 WORDLIST (2048 words)
750-900  SHA-256 (pure + hashlib)
900-1050 RIPEMD-160 (pure + hashlib)
1050-1100 HMAC-SHA-512
1100-1150 PBKDF2-HMAC-SHA512
1150-1250 secp256k1 (pure Python)
1250-1300 Base58Check
1300-1400 Bech32 (BIP173)
1400-1500 BIP32 CKD + derive_address
1500-1600 BIP39 helpers
1600-1700 Combo generators
1700-1800 Self-tests
1800-2000 Vault operations
2000-2100 Checkpoint helpers
2100-2200 Display helpers
2200-2250 Progress bar
2250-2400 Address database (Bloom + mmap)
2400-2600 Mode 1: Combo Generator
2600-2700 Mode 3: Mnemonic Verify
2700-2900 Hunt Mode
2900-3300 Mnemonic Hunt
3300-3700 Mnemonic Hunt R (Permutation)
3700-3900 Vault Browser
3900-4000 Main menu
4000+    __main__
```

### Naming Conventions

| Type | Convention | Example |
|------|-----------|---------|
| Constants | UPPER_CASE | `WORDLIST`, `_SHA256_K` |
| Functions | snake_case | `sha256()`, `vault_load()` |
| Internal | _leading_underscore | `_validate_indices()` |
| Classes | PascalCase | `BloomFilter`, `AddressDB` |
| Private attrs | _leading_underscore | `_bits`, `_m` |

---

## Adding a New Feature

### Example: Adding a New Address Type (BIP86)

1. **Add purpose constant:**
```python
purposes = {"BIP84":84, "BIP49":49, "BIP44":44, "BIP86":86}
```

2. **Add address encoding:**
```python
elif path_type == "BIP86":
    addr = bech32_encode("bc", h160)  # Same as BIP84 but different path
```

3. **Update `_derive_all_addresses`:**
```python
for pt in ["BIP86", "BIP84", "BIP49", "BIP44"]:
```

4. **Add test vector:**
```python
chk("BIP86 addr", derive_address(sd, "BIP86", 0, 0, 0)[0], "expected_address")
```

5. **Update documentation:**
- `README.md` — feature list
- `API_REFERENCE.md` — function docs
- `USER_GUIDE.md` — usage instructions

6. **Update CHANGELOG.md**

---

## Cryptographic Changes

### Rules

1. **Never modify existing primitives** — Add new ones instead
2. **Always include test vectors** — From official specs
3. **Verify against multiple sources** — Cross-check with other implementations
4. **Document the standard** — FIPS/ISO/RFC/BIP reference
5. **Get review** — Crypto changes require author (Neerugattu Venkatesh) approval

### Adding a New Hash Function

```python
def new_hash(data: bytes) -> bytes:
    """NewHash (FIPS XXX / RFC YYY).

    Implementation notes:
    - Uses stdlib X when available (C-accelerated)
    - Falls back to _new_hash_pure (verified)
    """
    try:
        return hashlib.new('newhash', data).digest()
    except Exception:
        return _new_hash_pure(data)
```

---

## Testing

### Running Tests

```bash
# All tests
python3 tests/test_crypto.py
python3 tests/test_bip_vectors.py
python3 tests/test_vault.py

# With pytest
pytest tests/

# Inline self-tests
python3 ORIGIN.py
# Select [T]
```

### Writing Tests

```python
def test_feature_name():
    """Description of what this tests."""
    # Setup
    input_data = b"test"

    # Execute
    result = function_under_test(input_data)

    # Verify
    expected = b"expected"
    assert result == expected, f"Expected {expected}, got {result}"
```

### Test Coverage Requirements

| Component | Coverage |
|-----------|----------|
| Crypto primitives | 100% (all test vectors) |
| BIP functions | 100% (all address types) |
| Vault operations | 90%+ |
| UI helpers | 70%+ |
| Hunt modes | 80%+ |

---

## Performance Optimization

### Profiling

```bash
# Time a specific function
python3 -m timeit -s "from ORIGIN import sha256" "sha256(b'test')"

# Profile the entire hunt
python3 -m cProfile -o hunt.prof ORIGIN.py
# Then: python3 -m pstats hunt.prof
```

### Hot Paths

| Function | Calls/iteration | Optimization |
|----------|----------------|--------------|
| `privkey_to_pubkey` | 3 (one per BIP type) | Install `coincurve` |
| `_validate_indices` | 1 | Already optimized (bit ops) |
| `index_to_combo` | 1 | Inline arithmetic |
| `addr in _ADDR_DB` | 3 | Bloom filter + set |

### Caching Strategy

```python
# Cache locals in hot loops (already done in hunt modes)
addr_db = _ADDR_DB
derive_all = _derive_all_addresses
build_record = _build_record
vault_add_fn = vault_add
```

---

## Debugging

### Common Issues

**Self-test fails:**
```python
# Add verbose debugging
print(f"DEBUG: sha256(b'') = {sha256(b'').hex()}")
print(f"DEBUG: expected = {expected}")
```

**Vault corruption:**
```python
# Inspect vault
python3 -c "import json; print(json.dumps(json.load(open('wallet_vault.json')), indent=2))"
```

**Address DB not loading:**
```python
# Check file
python3 -c "
with open('bruteaddress.txt', 'rb') as f:
    print(f'Size: {len(f.read())} bytes')
    f.seek(0)
    print(f'First line: {f.readline()}')
"
```

### Logging

ORIGIN uses `hunt_log.txt` for operational logging. For development, add temporary prints or use the `info()` function.

---

## Release Process

### Version Numbering

Follows [Semantic Versioning](https://semver.org/):
- `MAJOR.MINOR.PATCH`
- Pre-HORIZON: no version numbers (development)
- HORIZON: `1.0.0` (01 AUG 2026)

### Release Checklist

1. Update `CHANGELOG.md`
2. Update version references in all docs
3. Run all tests: `python3 tests/test_*.py`
4. Run self-tests: `python3 ORIGIN.py` → [T]
5. Test on all platforms (Linux, macOS, Windows)
6. Test with and without `coincurve`
7. Tag release: `git tag -a v1.0.0 -m "HORIZON release"`
8. Push: `git push origin v1.0.0`
9. Create GitHub release with notes

---

*End of Developer Guide*
