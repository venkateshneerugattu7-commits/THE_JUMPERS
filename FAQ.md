# Frequently Asked Questions — ORIGIN

> **Software:** ORIGIN — BIP39/BIP32/BIP44/BIP49/BIP84 Wallet Toolkit  
> **Author:** Neerugattu Venkatesh  
> **Organization:** THE JUMPERS

---

## General Questions

### Q: What is ORIGIN?

ORIGIN is a standalone Python toolkit for Bitcoin wallet recovery and research. It implements BIP39 (mnemonics), BIP32 (hierarchical deterministic wallets), and BIP44/49/84 (address derivation) entirely in pure Python with zero pip dependencies.

### Q: Who created ORIGIN?

ORIGIN was created by **Neerugattu Venkatesh** and is maintained by **THE JUMPERS** organization.

### Q: Is ORIGIN free?

Yes. ORIGIN is released under the MIT License. The author accepts donations at `bc1q5x9mwd352apqlqp23xdlulsndz9ceqgrjaw7aa` but this is entirely optional.

### Q: When is the next release?

**HORIZON** — scheduled for **01 AUG 2026**. See [CHANGELOG.md](../CHANGELOG.md) for planned features.

---

## Installation & Usage

### Q: Do I need to install anything?

No. ORIGIN requires only Python 3.8+. No `pip install` needed. Optional `coincurve` can be installed for 100x speedup.

```bash
python3 ORIGIN.py
```

### Q: How do I install coincurve for better performance?

```bash
pip install coincurve
```

The tool auto-detects and uses it. You'll see "coincurve acceleration is ACTIVE" in the self-test output.

### Q: Can I run this on Windows?

Yes. ORIGIN is cross-platform (Linux, macOS, Windows). File locking uses `msvcrt` on Windows and `fcntl` on Unix.

### Q: Can I run this in a Docker container?

Yes. See [DEPLOYMENT.md](DEPLOYMENT.md) for a Dockerfile and docker-compose example.

---

## Security

### Q: Is it safe to use ORIGIN with real wallets?

ORIGIN is designed for wallet recovery. For maximum safety:

1. Run on an air-gapped machine (no network)
2. Use a dedicated system or live OS
3. Protect the `wallet_vault.json` file
4. Always verify self-tests pass on startup

### Q: Does ORIGIN connect to the internet?

**No.** ORIGIN makes zero network connections. All operations are local.

### Q: Where are my keys stored?

Keys exist only in memory during derivation. If you save results to the vault, they are stored as plaintext JSON in `wallet_vault.json`. Protect this file.

### Q: What if the self-tests fail?

The program aborts immediately. Do NOT use it for real keys. Report the issue with the exact failure message.

### Q: Is the pure Python crypto secure?

The pure Python implementations are **correct** (verified against BIP vectors) but **not constant-time**. For production use, install `coincurve` which uses OpenSSL's hardened secp256k1.

---

## Features

### Q: What can ORIGIN do?

- **Combo Generator:** Create mnemonics from integer combinations
- **Mnemonic Verify:** Validate BIP39 checksums and derive addresses
- **Hunt Mode:** Scan combos against an address database
- **Mnemonic Hunt:** Pattern-based mnemonic scanning with checkpoints
- **Mnemonic Hunt R:** Permutation-mode scanning (no duplicate words)
- **Vault Browser:** Save, search, export, and manage results

### Q: What is `bruteaddress.txt`?

A text file containing Bitcoin addresses (one per line) that you want to search against. ORIGIN loads this into a Bloom filter + hash set for fast O(1) lookups.

### Q: How do I create `bruteaddress.txt`?

You can generate it from blockchain data, use public datasets, or create it manually. One address per line, ASCII only. Lines starting with `#` are ignored.

### Q: What are checkpoints?

Checkpoints save your hunt progress every 500,000 iterations. If the program crashes or is interrupted, you can resume from the last checkpoint. Checkpoints are stored as `hunt_checkpoint_*.json`.

### Q: How do I pause a running hunt?

Create a file named `hunt_pause.flag` in the same directory. The hunt will pause until you delete the file. This works even for background processes.

---

## Performance

### Q: How fast is ORIGIN?

| Configuration | Speed |
|---------------|-------|
| Pure Python | ~6 addresses/second |
| With coincurve | ~500 addresses/second |
| Address DB lookup | ~1 microsecond |

### Q: How much memory does the address database use?

| Component | Memory per 1M addresses |
|-----------|----------------------|
| Bloom filter | ~1 MB |
| Python set | ~50 MB |
| **Total** | **~51 MB** |

### Q: Can I hunt with multiple processes?

Not yet built-in, but you can run multiple instances with different rank ranges. Future HORIZON release will add native multi-processing.

---

## Troubleshooting

### Q: "bruteaddress.txt not found"

Create the file: `touch bruteaddress.txt` or place your address list in the same directory as `ORIGIN.py`.

### Q: "CRYPTO SELF-TEST FAILED"

Do not use the tool. Check:
1. Python version (need 3.8+)
2. File integrity (`sha256sum ORIGIN.py`)
3. If `coincurve` is installed, try removing it temporarily

### Q: Very slow performance

1. Install `coincurve`: `pip install coincurve`
2. Reduce "Addresses per type" in hunt settings
3. Filter `bruteaddress.txt` to only needed address types

### Q: Vault won't save

Check:
1. Disk space: `df -h .`
2. File permissions: `ls -la wallet_vault.json`
3. Directory permissions

---

## Contributing

### Q: Can I contribute?

Yes! See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

### Q: How do I report a bug?

Open a GitHub issue with:
- Python version and OS
- Steps to reproduce
- Expected vs actual behavior
- Self-test output (`[T]` menu option)

### Q: How do I report a security vulnerability?

See [SECURITY.md](../SECURITY.md). Do NOT open a public issue.

---

## Donations

### Q: How can I support ORIGIN?

Bitcoin donations are accepted at:

```
bc1q5x9mwd352apqlqp23xdlulsndz9ceqgrjaw7aa
```

> "Buy me coffee only if this helped to find your forgotten wallet. Your support keeps THE JUMPERS free for everyone."

---

*Last updated: 2026-06-24*
