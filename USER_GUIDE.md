# User Guide — ORIGIN

> **Software:** ORIGIN — BIP39/BIP32/BIP44/BIP49/BIP84 Wallet Toolkit  
> **Author:** Neerugattu Venkatesh  
> **Organization:** THE JUMPERS  
> **Version:** Pre-HORIZON (HORIZON: 01 AUG 2026)

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Mode 1: Combo Generator](#mode-1-combo-generator)
3. [Mode 3: Mnemonic Verify](#mode-3-mnemonic-verify)
4. [Mode S: Hunt Mode](#mode-s-hunt-mode)
5. [Mode M: Mnemonic Hunt](#mode-m-mnemonic-hunt)
6. [Mode U: Mnemonic Hunt R (Permutation)](#mode-u-mnemonic-hunt-r)
7. [Mode V: Vault Browser](#mode-v-vault-browser)
8. [Mode T: Self-Tests](#mode-t-self-tests)
9. [Tips & Tricks](#tips--tricks)

---

## Getting Started

### Running ORIGIN

```bash
python3 ORIGIN.py
```

You'll see the main menu:

```
════════════════════════════════════════════════════════════════════════════
║   BIP39 / BIP32 / BIP44 / BIP49 / BIP84   WALLET TOOLKIT                 ║
════════════════════════════════════════════════════════════════════════════
  ● Vault: 0 records   ○ coincurve: not installed
  ○ bruteaddress.txt: not loaded
────────────────────────────────────────────────────────────────────────────

  1  Combo Generator      SHA256(combo)->mnemonic->addresses
  3  Mnemonic Verify       validate + derive all 3 address types
  S  Hunt Mode             scan combos vs bruteaddress.txt
  M  Mnemonic Hunt         scan mnemonic patterns
  U  Mnemonic Hunt R       permutation scanner
  V  Vault Browser         search / export / manage saved results
  T  Run Self-Tests        verify crypto against official BIP vectors
  Q  Quit

  Tip: type H at any prompt to jump back here instantly
  Tip: create hunt_pause.flag to pause any running hunt
  Tip: matches + sessions logged to hunt_log.txt
```

### Navigation Tips

- **H** at any prompt → jump to main menu instantly
- **Enter** → accept default value (shown in brackets)
- **Ctrl+C** → interrupt current operation (saves checkpoint in hunt modes)

---

## Mode 1: Combo Generator

Generate BIP39 mnemonics from integer combinations.

### How It Works

```
Combo [4, 42, 5, 89, ...] → SHA-256 → Entropy → Mnemonic → Addresses
```

### Step-by-Step

1. Select **1** from main menu
2. Choose default ranges or enter custom ones:
   ```
   Slot 1 (min max, blank=done): 4 42
   Slot 2 (min max, blank=done): 5 89
   ...
   ```
3. Choose iteration order:
   - **1** Ascending (min→max)
   - **2** Descending (max→min)
   - **3** Exact combo only
   - **4** From exact combo upward
   - **5** From exact combo downward
4. Set max iterations (0 = unlimited)
5. Enter BIP39 passphrase (blank = none)
6. Set account, change, and addresses per type
7. Choose auto-save to vault

### Example Output

```
════════════════════════════════════════════════════════════════════════════
#1  combo [4, 42, 5, 89, 4, 61, 6, 74]  entropy c55257c3...
    1.abandon   2.abandon   3.ability   4.able    5.about   6.above
    7.absent    8.absorb    9.abstract  10.absurd 11.abuse  12.access

    ──── BIP84 ──── m/84'/0'/…
    m/84'/0'/0'/0/0              bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu
    m/84'/0'/0'/0/1              bc1qnjg0jd8228aq7egyzacy8cys3knf9xvrerkf9g
    m/84'/0'/0'/0/2              bc1q8c6fshw2dlwun7ekn9qwf37cu2rn755upcp6el

    ──── BIP49 ──── m/49'/0'/…
    m/49'/0'/0'/0/0              37VucYSaXLCAsxYyAPfbSi9eh4iEcbShgf
    ...
```

---

## Mode 3: Mnemonic Verify

Validate a BIP39 mnemonic and derive all address types.

### Step-by-Step

1. Select **3** from main menu
2. Enter your mnemonic (12/15/18/21/24 words)
3. ORIGIN validates the checksum
4. Enter passphrase (if any)
5. Set account, change, and address count
6. View derived addresses
7. Optionally save to vault

### Example

```
════════════════════════════════════════════════════════════════════════════
MODE 3  —  MNEMONIC VERIFY & DERIVE
────────────────────────────────────────────────────────────────────────────
Enter Mnemonic
  · Type or paste your BIP39 mnemonic (12/15/18/21/24 words)
  » Mnemonic: abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about

  Word count: 12

Validation
  ✓  BIP39 checksum VALID

  » BIP39 passphrase (blank=none): 
  » Account index [0]: 
  » Change index (0=ext, 1=int) [0]: 
  » Addresses per type [5]: 

  Seed (hex):
    c55257c360c07c72029aebc1b53c05ed0362ada38ead3e3e9efa3708e534d31e...

Derived Addresses
    ──── BIP84 ──── m/84'/0'/…
    m/84'/0'/0'/0/0              bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu
    ...
```

---

## Mode S: Hunt Mode

Scan combo ranges against `bruteaddress.txt` to find matching addresses.

### Prerequisites

Create `bruteaddress.txt` with target addresses:

```bash
echo "bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu" > bruteaddress.txt
echo "37VucYSaXLCAsxYyAPfbSi9eh4iEcbShgf" >> bruteaddress.txt
```

### Step-by-Step

1. Select **S** from main menu
2. ORIGIN loads the address database (first time only)
3. Choose default or custom combo ranges
4. Select ascending or descending order
5. Enter passphrase, account, change, addresses per type
6. Hunt begins with progress bar and ETA

### During the Hunt

```
████████████████░░░░  45.23%  Raw 4,523,000/10,000,000  1.2K/s  ETA 01:15:30  Matched 0  Combo [4,42,5]…
```

### If a Match is Found

```
  ★ FOUND: bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu
  combo    : [4, 42, 5, 89, 4, 61, 6, 74]
  path     : m/84'/0'/0'/0/0
  type     : BIP84
  ✓  Auto-saved → combo [4, 42, 5, 89, 4, 61, 6, 74]
```

### Pausing

```bash
# In another terminal:
touch hunt_pause.flag

# To resume:
rm hunt_pause.flag
```

---

## Mode M: Mnemonic Hunt

Scan mnemonic patterns with unknown word positions.

### Use Case

You remember some words of your mnemonic but not all. For example:
- "abandon ? ability ? about ? absent ? abstract ?"

### Step-by-Step

1. Select **M** from main menu
2. Choose word count (12/15/18/21/24)
3. For each word, enter the word or `?` for unknown
4. For unknown slots, provide candidates:
   - `all` — all 2048 words
   - `0-100` — index range
   - `word1, word2, 42` — specific words/indices
5. Configure scan settings (passphrase, account, etc.)
6. Choose duplicate word filter
7. Select scan mode (full or custom range)
8. Hunt begins with checkpoint support

### Example Pattern

```
Word 1 (word or '?'): abandon
Word 2 (word or '?'): ?
  Candidates for slot 2 (words/idx/a-b/all): all
    → 2048 candidates for slot 2
Word 3 (word or '?'): ability
Word 4 (word or '?'): ?
  Candidates for slot 4 (words/idx/a-b/all): 0-100
    → 101 candidates for slot 4
...
```

### Progress Display

```
████████████████░░░░  12.34%  Raw 1,234,567/10,000,000  Valid 12,340(0.1234%)  850/s  ETA 02:30:00  Hits 0
```

### Checkpoints

Checkpoints save every 500,000 iterations. On restart, ORIGIN asks:

```
Checkpoint found at rank 1,234,567. Resume? [Y/n]: 
```

---

## Mode U: Mnemonic Hunt R (Permutation)

Same as Mode M, but unknown slots are filled **without replacement** from a shared pool.

### Difference from Mode M

| Mode | Behavior | Use Case |
|------|----------|----------|
| M | Independent choice per slot (with replacement) | General pattern matching |
| R | Pool of candidates, draw without replacement | You know all words are unique |

### Example

If your mnemonic has no duplicate words, Mode R is more efficient because it skips permutations with repeats.

---

## Mode V: Vault Browser

Manage saved results.

### Menu Options

```
VAULT BROWSER  —  PERSISTENT MEMORY

  Vault file : /path/to/wallet_vault.json
  Records    : 5
  Addresses  : 15
  First saved: 2026-06-24T08:00:00
  Last saved : 2026-06-24T10:30:00

Vault Actions
  1  Browse all records
  2  Search by address
  3  Search by keyword
  4  Delete a record
  5  Export to CSV
  6  Export to TXT
  7  Add / edit note on a record
  B  Back to main menu
```

### Export Formats

**CSV:**
```csv
timestamp,combo,mnemonic,type,path,address,note
2026-06-24T08:00:00,"[4,42,5,89]","abandon abandon...",BIP84,m/84'/0'/0'/0/0,bc1q...,HUNT MATCH
```

**TXT:** Human-readable with formatting.

---

## Mode T: Self-Tests

Verify all cryptographic primitives against official BIP test vectors.

### When to Run

- **Automatically** on every startup (silent mode)
- **Manually** by selecting **T** from main menu (verbose mode)
- **After any code modification**
- **When怀疑 crypto correctness**

### Expected Output

```
════════════════════════════════════════════════════════════════════════════
SELF-TEST — OFFICIAL BIP VECTORS
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

### If Tests Fail

```
  ✗  BIP84 addr
       exp: bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu
       got: bc1qxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

  ✗  1 test(s) FAILED — do not use for real keys
```

**Do not proceed.** Report the issue immediately.

---

## Tips & Tricks

### Speed Optimization

1. **Install coincurve**: `pip install coincurve` → 100x speedup
2. **Reduce addr_count**: Set to 1 instead of 5 in hunt settings
3. **Filter address DB**: Pre-filter `bruteaddress.txt` to needed types
4. **Use checkpoints**: Resume instead of restarting

### Memory Optimization

1. **Filter bruteaddress.txt**: Keep only relevant address types
2. **Use smaller candidate lists**: Narrow down unknown words
3. **Close other applications**: Free RAM for the address set

### Security Best Practices

1. **Air-gap the machine**: Disconnect from internet
2. **Use dedicated hardware**: Old laptop, live OS
3. **Protect the vault**: `chmod 600 wallet_vault.json`
4. **Verify before trusting**: Always run self-tests
5. **Never share**: Keep mnemonics private

### Common Patterns

**Recovering a forgotten mnemonic with known words:**
```
Mode M → 12 words →
  Word 1: abandon
  Word 2: ? (candidates: all)
  Word 3: ability
  Word 4: ? (candidates: 0-500)
  ...
```

**Brute-forcing a combo seed:**
```
Mode S → Default ranges →
  Ascending → Max iterations: 1000000
```

**Verifying a paper backup:**
```
Mode 3 → Enter mnemonic →
  Compare derived addresses with your wallet
```

---

*End of User Guide*
