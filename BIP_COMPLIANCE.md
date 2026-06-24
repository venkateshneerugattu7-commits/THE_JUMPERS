# BIP Compliance & Test Vectors — ORIGIN

> **Software:** ORIGIN — BIP39/BIP32/BIP44/BIP49/BIP84 Wallet Toolkit  
> **Author:** Neerugattu Venkatesh  
> **Organization:** THE JUMPERS  
> **Version:** Pre-HORIZON (HORIZON: 01 AUG 2026)

---

## Overview

ORIGIN verifies every cryptographic primitive against official Bitcoin Improvement Proposal (BIP) test vectors on every startup. If any test fails, the program aborts immediately with a detailed error report.

This document catalogs all verified test vectors and their sources.

---

## SHA-256 (FIPS 180-4)

### Test Vector 1: Empty String

| Field | Value |
|-------|-------|
| Input | `b''` |
| Expected | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| Source | NIST CAVP |

### Test Vector 2: "abc"

| Field | Value |
|-------|-------|
| Input | `b'abc'` |
| Expected | `ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad` |
| Source | NIST CAVP |

**Verification:** `run_tests()` calls `chk("SHA-256 empty", sha256(b'').hex(), expected)`

---

## RIPEMD-160 (ISO/IEC 10118-3)

### Test Vector 1: Empty String

| Field | Value |
|-------|-------|
| Input | `b''` |
| Expected | `9c1185a5c5e9fc54612808977ee8f548b2258d31` |
| Source | ISO/IEC 10118-3 official vectors |

### Test Vector 2: "abc"

| Field | Value |
|-------|-------|
| Input | `b'abc'` |
| Expected | `8eb208f7e05d987a9b044a8e98c6b087f15a0bfc` |
| Source | ISO/IEC 10118-3 official vectors |

**OpenSSL Detection:** At import time, ORIGIN probes whether `hashlib.new('ripemd160')` produces correct output. Some OpenSSL 3.x builds disable legacy digests or return wrong values. If the probe fails, the pure Python implementation is used transparently.

---

## HMAC-SHA-512 & BIP32 Master Key

### Test Vector: BIP32 Seed 00010203...

| Field | Value |
|-------|-------|
| Seed | `000102030405060708090a0b0c0d0e0f` |
| Master Private Key | `e8f32e723decf4051aefac8e2c93c9c5b214313817cdb01a1494b917c8436b35` |
| Master Chain Code | `873dff81c02f525623fd1fe5167eac3a55a049de3d314bb42ee227ffed37d508` |
| Source | BIP-0032 Test Vector 1 |

**Verification:**
```python
raw = hmac_sha512(b"Bitcoin seed", bytes.fromhex("000102030405060708090a0b0c0d0e0f"))
chk("BIP32 master priv", raw[:32].hex(), expected_priv)
chk("BIP32 master chain", raw[32:].hex(), expected_chain)
```

---

## BIP39 Seed Generation

### Test Vector: "abandon abandon ... about"

| Field | Value |
|-------|-------|
| Mnemonic | `abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about` |
| Passphrase | `""` |
| Seed (first 64 hex) | `c55257c360c07c72029aebc1b53c05ed0362ada38ead3e3e9efa3708e534d31e` |
| Source | BIP-0039 official vectors |

---

## BIP44 Address Derivation

### Test Vector: P2PKH

| Field | Value |
|-------|-------|
| Path | `m/44'/0'/0'/0/0` |
| Address | `1LqBGSKuX5yYUonjxT5qGfpUsXKYYWeabA` |
| Source | BIP-0044 test vectors |

**Verification:**
```python
sd = mnemonic_to_seed(mn, "")
chk("BIP44 addr", derive_address(sd, "BIP44", 0, 0, 0)[0], "1LqBGSKuX5yYUonjxT5qGfpUsXKYYWeabA")
```

---

## BIP49 Address Derivation

### Test Vector: P2SH-P2WPKH

| Field | Value |
|-------|-------|
| Path | `m/49'/0'/0'/0/0` |
| Address | `37VucYSaXLCAsxYyAPfbSi9eh4iEcbShgf` |
| Source | BIP-0049 test vectors |

**Verification:**
```python
chk("BIP49 addr", derive_address(sd, "BIP49", 0, 0, 0)[0], "37VucYSaXLCAsxYyAPfbSi9eh4iEcbShgf")
```

---

## BIP84 Address Derivation

### Test Vector: P2WPKH (Native SegWit)

| Field | Value |
|-------|-------|
| Path | `m/84'/0'/0'/0/0` |
| Address | `bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu` |
| Source | BIP-0084 test vectors |

**Verification:**
```python
chk("BIP84 addr", derive_address(sd, "BIP84", 0, 0, 0)[0], "bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu")
```

---

## BIP39 Validation

### Test Vector 1: Valid Checksum

| Field | Value |
|-------|-------|
| Mnemonic | `abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about` |
| Expected | `True` |

### Test Vector 2: Invalid Checksum

| Field | Value |
|-------|-------|
| Mnemonic | `abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon XXXXX` |
| Expected | `False` |

**Verification:**
```python
chk("BIP39 valid cs", validate_mnemonic(mn), True)
chk("BIP39 reject bad", validate_mnemonic("abandon "*11+"XXXXX"), False)
```

---

## BIP173 Bech32 Encoding

### Test Vector: P2WPKH Address

| Field | Value |
|-------|-------|
| HRP | `bc` |
| Witness Program | `751e76e8199196d454941c45d1b3a323f1433bd6` |
| Address | `bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu` |
| Source | BIP-0173 test vectors |

**Indirect Verification:** Via BIP84 address derivation test above.

---

## BIP32 Extended Key Serialization

ORIGIN does not implement extended key (xpub/xprv) serialization. It derives addresses directly from the seed. However, the underlying BIP32 derivation (CKD) is verified via the master key test vector above.

For full extended key test vectors, see:
- BIP-0032 Test Vector 1: `00010203...` seed
- BIP-0032 Test Vector 2: `ffff...` seed
- BIP-0032 Test Vector 3: Leading zeros test
- BIP-0032 Test Vector 4: Leading zeros test (alternate)
- BIP-0032 Test Vector 5: Invalid key tests

---

## BIP84 Extended Key Version Bytes

| Key Type | Version Bytes | Prefix |
|----------|--------------|--------|
| zpub | `0x04b24746` | zpub |
| zprv | `0x04b2430c` | zprv |
| vpub (testnet) | `0x045f1cf6` | vpub |
| vprv (testnet) | `0x045f18bc` | vprv |

ORIGIN does not serialize extended keys, but uses the same derivation paths as BIP84.

---

## Verification on Startup

```python
def run_tests(silent=False):
    results = []
    def chk(name, got, exp):
        p = (got == exp)
        results.append((name, p, got, exp))
        return p

    # Run all tests...

    passed = sum(1 for _, p, _, _ in results if p)
    failed = len(results) - passed

    if failed > 0:
        err(f"{failed} test(s) FAILED — do not use for real keys")
        return False
    return True
```

**Called from main_menu():**
```python
if not run_tests(silent=True):
    err("CRYPTO SELF-TEST FAILED — Aborting for safety.")
    sys.exit(1)
```

---

## Running Tests Manually

From the main menu, select `[T] Run Self-Tests` for verbose output:

```
════════════════════════════════════════════════════════════════════════════
║           SELF-TEST — OFFICIAL BIP VECTORS                               ║
════════════════════════════════════════════════════════════════════════════
  ✓  SHA-256 empty
  ✓  SHA-256 abc
  ✓  RIPEMD-160 empty
  ✓  RIPEMD-160 abc
  ✓  BIP32 master priv
  ✓  BIP32 master chain
  ✓  BIP44 addr
  ✓  BIP49 addr
  ✓  BIP84 addr
  ✓  BIP39 valid cs
  ✓  BIP39 reject bad

  ✓  All 11 tests passed — crypto verified correct
  ·  coincurve acceleration is ACTIVE
```

---

## References

| BIP | Title | Author | Status |
|-----|-------|--------|--------|
| [BIP-0032](https://github.com/bitcoin/bips/blob/master/bip-0032.mediawiki) | Hierarchical Deterministic Wallets | Pieter Wuille | Final |
| [BIP-0039](https://github.com/bitcoin/bips/blob/master/bip-0039.mediawiki) | Mnemonic Code for Generating Deterministic Keys | Marek Palatinus, Pavol Rusnak, Aaron Voisine, Sean Bowe | Final |
| [BIP-0044](https://github.com/bitcoin/bips/blob/master/bip-0044.mediawiki) | Multi-Account Hierarchy for Deterministic Wallets | Marek Palatinus, Pavol Rusnak | Final |
| [BIP-0049](https://github.com/bitcoin/bips/blob/master/bip-0049.mediawiki) | Derivation scheme for P2WPKH-nested-in-P2SH | Daniel Weigl | Final |
| [BIP-0084](https://github.com/bitcoin/bips/blob/master/bip-0084.mediawiki) | Derivation scheme for P2WPKH based accounts | Pavol Rusnak | Final |
| [BIP-0173](https://github.com/bitcoin/bips/blob/master/bip-0173.mediawiki) | Base32 address format for native v0-16 witness outputs | Pieter Wuille, Greg Maxwell | Final |

---

*End of BIP Compliance Document*
