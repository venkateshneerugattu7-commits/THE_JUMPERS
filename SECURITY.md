# Security Policy

## Supported Versions

| Version | Status | Notes |
|---------|--------|-------|
| HORIZON (upcoming) | Planned | Release: 01 AUG 2026 |
| Current | Active | All security patches applied |

## Security Model

ORIGIN is a **local-only, offline** wallet toolkit:

- No network connections are ever made
- All keys are generated deterministically from user input
- Vault is stored as plaintext JSON on local disk
- No OS entropy is used for generation (user provides combos/patterns)

## Threat Model

### In Scope

- Cryptographic correctness (BIP compliance)
- Memory safety (keys in RAM)
- File locking race conditions
- Vault file integrity

### Out of Scope

- Physical access to the machine (protect your OS)
- Malware/keyloggers (use in isolated environments)
- Weak user-chosen passphrases
- Social engineering

## Reporting a Vulnerability

**Please do NOT open a public issue for security vulnerabilities.**

Instead:

1. Email: [security@thejumpers.dev] (or contact Neerugattu Venkatesh directly)
2. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact assessment
   - Suggested fix (if any)
3. Allow **90 days** for disclosure before public discussion

## Response Process

1. Acknowledge receipt within 48 hours
2. Validate and assess severity within 7 days
3. Develop and test fix
4. Release patched version
5. Publicly disclose with CVE (if applicable) after fix is available

## Security Best Practices for Users

1. **Run offline** — disconnect from internet when generating/recovering keys
2. **Use a dedicated machine** — ideally a live OS or air-gapped system
3. **Protect the vault** — `wallet_vault.json` contains plaintext keys
4. **Verify checksums** — always run self-tests (`[T]` menu option)
5. **Never share** — mnemonics, seeds, or private keys with anyone
6. **Audit the code** — this is open source; verify before trusting

## Known Limitations

- **Pure Python secp256k1** is timing-attackable (use `coincurve` for production)
- **No side-channel resistance** — not hardened against power analysis
- **Vault is unencrypted** — rely on OS-level file permissions
- **Deterministic generation** — same input always produces same output

## Cryptographic Verification

Every startup runs self-tests against official BIP vectors:

| Test | Vector Source | Status |
|------|-------------|--------|
| SHA-256 | NIST CAVP | ✅ Verified |
| RIPEMD-160 | ISO/IEC 10118-3 | ✅ Verified |
| HMAC-SHA-512 | BIP-0032 | ✅ Verified |
| BIP39 Seed | BIP-0039 | ✅ Verified |
| BIP44 Address | BIP-0044 | ✅ Verified |
| BIP49 Address | BIP-0049 | ✅ Verified |
| BIP84 Address | BIP-0084 | ✅ Verified |

If any test fails, the program aborts immediately.

## Security History

| Date | Issue | Severity | Status |
|------|-------|----------|--------|
| None reported | — | — | — |

---

**Responsible disclosure is appreciated. Thank you for helping keep ORIGIN users safe.**

— Neerugattu Venkatesh, THE JUMPERS
