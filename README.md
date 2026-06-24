# ORIGIN

> **BIP39 / BIP32 / BIP44 / BIP49 / BIP84 Wallet Toolkit**
> 
> Pure Python cryptocurrency wallet toolkit with zero pip dependencies.
> Optional `coincurve` acceleration for 100x faster secp256k1 operations.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Crypto Verified](https://img.shields.io/badge/crypto-verified%20against%20BIP%20vectors-success)](.)

---

## Overview

**ORIGIN** is a standalone, zero-dependency Bitcoin wallet toolkit developed by **Neerugattu Venkatesh** at **THE JUMPERS**. It implements the full BIP39/BIP32/BIP44/BIP49/BIP84 derivation stack entirely in pure Python — no `pip install` required. Every cryptographic primitive (SHA-256, RIPEMD-160, HMAC-SHA-512, PBKDF2, secp256k1, Base58Check, Bech32) is implemented from scratch and verified against official BIP test vectors.

If `coincurve` is installed, secp256k1 point multiplication is automatically accelerated up to **100x**.

---

## Features

| Feature | Description |
|---------|-------------|
| **Combo Generator** | SHA-256(combo) → BIP39 mnemonic → derive addresses (BIP44/49/84) |
| **Mnemonic Verify** | Validate BIP39 checksum + derive all 3 address types |
| **Hunt Mode** | Brute-force scan combo ranges against `bruteaddress.txt` |
| **Mnemonic Hunt (M)** | Pattern-based mnemonic scanner with checkpoints, ETA, and pause |
| **Mnemonic Hunt R (U)** | Permutation-mode scanner (words drawn without replacement) |
| **Vault Browser** | Persistent JSON storage with search, export (CSV/TXT), and notes |
| **Self-Tests** | Automatic verification against official BIP test vectors on every startup |
| **Bloom Filter** | Memory-efficient address database with O(1) lookups |
| **Checkpoint System** | Resume long-running scans from any point |
| **Cross-Platform** | Works on Linux, macOS, Windows with native file locking |

---

## Quick Start

# Clone the repository

git clone https://github.com/venkateshneerugattu7-commits/THE_JUMPERS.git
cd THE_JUMPERS

# Run (zero dependencies)

python ORIGIN.py

# Optional: install coincurve for 100x speedup

pip install coincurve


## Architecture

```
ORIGIN/
├── ORIGIN.py              # Main application (single file, ~3000 lines)
├── bruteaddress.txt       # Target address database (one per line)
├── wallet_vault.json      # Persistent vault (auto-created)
├── hunt_log.txt           # Match + session log (auto-created)
├── hunt_pause.flag        # Pause signal file (create to pause hunts)
├── hunt_checkpoint_*.json # Resume checkpoints (auto-created)
├── README.md              # This file
├── LICENSE                # MIT License
├── CONTRIBUTING.md        # Contribution guidelines
├── SECURITY.md            # Security policy and responsible disclosure
├── CHANGELOG.md           # Version history
├── docs/
│   ├── API_REFERENCE.md   # Function-level documentation
│   ├── ARCHITECTURE.md    # Deep-dive into design decisions
│   ├── BIP_COMPLIANCE.md  # Test vector verification details
│   └── DEPLOYMENT.md      # Production deployment guide
└── tests/
    ├── test_crypto.py     # Cryptographic primitive tests
    ├── test_bip_vectors.py # Official BIP test vectors
    └── test_vault.py      # Vault persistence tests
```

---

## Cryptographic Primitives (Pure Python)

All primitives are implemented from first principles and verified against official test vectors:

| Primitive | Standard | Verification |
|-----------|----------|------------|
| SHA-256 | FIPS 180-4 | `e3b0c442...` (empty), `ba7816bf...` (abc) |
| RIPEMD-160 | ISO/IEC 10118-3 | `9c1185a5...` (empty), `8eb208f7...` (abc) |
| HMAC-SHA-512 | RFC 2104 | BIP32 master key derivation |
| PBKDF2-HMAC-SHA512 | RFC 2898 | BIP39 seed generation |
| secp256k1 | SECG | BIP32/44/49/84 address derivation |
| Base58Check | Bitcoin | P2PKH / P2SH address encoding |
| Bech32 (BIP173) | BIP-0173 | SegWit v0 address encoding |

---

## Modes of Operation

### 1. Combo Generator
Generate mnemonics from integer combinations. Each combo is hashed via SHA-256 to produce entropy, then converted to a BIP39 mnemonic.

```
Combo → SHA-256 → Entropy → Mnemonic → Seed → Addresses (BIP44/49/84)
```

### 2. Hunt Mode (S)
Scan combo ranges against a target address database (`bruteaddress.txt`). Uses a Bloom filter + hash set for O(1) lookups with minimal memory.

### 3. Mnemonic Hunt (M)
Pattern-based scanning with unknown word positions. Supports:
- Candidate lists per slot (words, indices, ranges, or "all")
- Duplicate word filtering
- Progress bar with ETA and speed
- Checkpoint/resume every 500K iterations
- Pause via `hunt_pause.flag`

### 4. Mnemonic Hunt R (U)
Permutation mode: unknown slots are filled from a shared pool **without replacement**, ensuring no duplicate words across unknown positions.

### 5. Vault Browser (V)
Persistent JSON storage with:
- Atomic read-modify-write with file locking
- Search by address, keyword, or combo
- Export to CSV / TXT
- Add/edit notes on records

---

## Performance

| Operation | Pure Python | With coincurve |
|-----------|-------------|----------------|
| secp256k1 point multiply | ~50 ms | ~0.5 ms |
| Address derivation (1 addr) | ~150 ms | ~2 ms |
| Hunt throughput | ~6 addr/s | ~500 addr/s |
| Bloom filter lookup | ~1 μs | ~1 μs |
| Vault write (locked) | ~5 ms | ~5 ms |

*Benchmarks on Intel i7-12700H, Python 3.11*

---

## File Locking

Cross-platform advisory locking ensures safe concurrent access:

| Platform | Method | Behavior |
|----------|--------|----------|
| Linux/macOS | `fcntl.flock()` | Blocking exclusive/shared locks |
| Windows | `msvcrt.locking()` | Retry loop with indefinite wait |
| Other | No-op | Best-effort (single-process safe) |

---

## Security Considerations

⚠️ **This tool is designed for wallet recovery and research. Never use it on production systems without understanding the risks.**

- All keys are generated in memory only (no network calls)
- Vault is stored as plaintext JSON — protect the file
- No entropy is collected from the OS; combos are deterministic
- Self-tests run on every startup to detect tampering
- See [SECURITY.md](SECURITY.md) for full policy

---

## Contributing

We welcome contributions! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on:
- Code style (PEP 8 + project conventions)
- Pull request process
- Issue reporting
- Security disclosures

---

## License

MIT License — see [LICENSE](LICENSE) for details.

Copyright (c) 2026 Neerugattu Venkatesh, THE JUMPERS

---

## Acknowledgments

- BIP authors: Pieter Wuille, Marek Palatinus, Pavol Rusnak, Aaron Voisine, Sean Bowe
- `coincurve` by Ofek Lev for optional C-accelerated secp256k1
- The Bitcoin community for open standards and test vectors

---

## Contact

- **Author:** Neerugattu Venkatesh
- **Organization:** THE JUMPERS
- **Donate:** `bc1q5x9mwd352apqlqp23xdlulsndz9ceqgrjaw7aa`
- **Next Release:** HORIZON — 01 AUG 2026

> *"Buy me coffee only if this helped to find your forgotten wallet. Your support keeps THE JUMPERS free for everyone."*
