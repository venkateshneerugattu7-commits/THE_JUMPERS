# Deployment Guide — ORIGIN

> **Software:** ORIGIN — BIP39/BIP32/BIP44/BIP49/BIP84 Wallet Toolkit  
> **Author:** Neerugattu Venkatesh  
> **Organization:** THE JUMPERS  
> **Version:** Pre-HORIZON (HORIZON: 01 AUG 2026)

---

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Installation](#installation)
3. [Air-Gapped Deployment](#air-gapped-deployment)
4. [Performance Tuning](#performance-tuning)
5. [Running as a Service](#running-as-a-service)
6. [Docker Deployment](#docker-deployment)
7. [Security Hardening](#security-hardening)
8. [Monitoring](#monitoring)
9. [Backup & Recovery](#backup--recovery)
10. [Troubleshooting](#troubleshooting)

---

## System Requirements

### Minimum

| Resource | Requirement |
|----------|-------------|
| Python | 3.8+ |
| RAM | 512 MB |
| Disk | 100 MB |
| OS | Linux, macOS, Windows |

### Recommended (for large hunts)

| Resource | Requirement |
|----------|-------------|
| Python | 3.11+ (faster) |
| RAM | 8 GB (for 100M+ address DB) |
| Disk | 50 GB (for address database) |
| CPU | Multi-core (hunts are single-threaded, but vault/DB loading benefits) |
| Optional | `coincurve` for 100x speedup |

---

## Installation

### Method 1: Direct Download (Recommended)

```bash
# Download the single file
curl -O https://raw.githubusercontent.com/THEJUMPERS/ORIGIN/main/ORIGIN.py

# Make executable
chmod +x ORIGIN.py

# Run
python3 ORIGIN.py
```

### Method 2: Git Clone

```bash
git clone https://github.com/THEJUMPERS/ORIGIN.git
cd ORIGIN
python3 ORIGIN.py
```

### Method 3: With coincurve (Performance)

```bash
# Install optional dependency
pip install coincurve

# Verify acceleration is active
python3 ORIGIN.py
# Menu will show: "coincurve: active"
```

---

## Air-Gapped Deployment

For maximum security when handling real keys:

### 1. Prepare the Machine

```bash
# Use a dedicated machine or live OS (Tails, Ubuntu Live)
# Disable networking entirely
sudo systemctl stop NetworkManager
sudo ip link set lo down

# Verify no network interfaces are up
ip addr show
```

### 2. Transfer Files

```bash
# Use USB drive (never network)
# Copy ORIGIN.py and bruteaddress.txt to the machine
# Verify file integrity:
sha256sum ORIGIN.py
# Compare with published hash
```

### 3. Run in Isolated Environment

```bash
# Create a dedicated user
sudo useradd -m -s /bin/bash origin
sudo su - origin

# Run with restricted permissions
python3 /path/to/ORIGIN.py
```

### 4. Output Handling

```bash
# Save vault to encrypted USB
# Never connect the machine to network after running
cp wallet_vault.json /mnt/encrypted_usb/
umount /mnt/encrypted_usb
```

---

## Performance Tuning

### Without coincurve (Pure Python)

```bash
# Expected throughput: ~6 addresses/second
# Suitable for: Small searches, verification, testing

# Optimize by reducing addr_count:
# In hunt settings, set "Addresses per type" to 1 instead of 5
```

### With coincurve

```bash
# Expected throughput: ~500 addresses/second
# Suitable for: Large-scale hunts, production recovery

pip install coincurve

# Verify:
python3 -c "import coincurve; print('OK')"
```

### Address Database Optimization

```bash
# Pre-filter bruteaddress.txt to only relevant address types
# If you only need bc1q addresses:
grep '^bc1q' bruteaddress_full.txt > bruteaddress.txt

# This reduces memory and load time significantly
```

### Memory Limits

```bash
# For systems with limited RAM, process address DB in chunks
# ORIGIN loads the entire DB into memory
# Bloom filter: ~1MB per 1M addresses
# Python set: ~50MB per 1M addresses

# Example: 100M addresses = ~5GB RAM
ulimit -v 6000000  # 6GB virtual memory limit
python3 ORIGIN.py
```

---

## Running as a Service

### systemd Service (Linux)

Create `/etc/systemd/system/origin-hunt.service`:

```ini
[Unit]
Description=ORIGIN Wallet Hunt
After=network.target

[Service]
Type=simple
User=origin
WorkingDirectory=/opt/origin
ExecStart=/usr/bin/python3 /opt/origin/ORIGIN.py
Restart=on-failure
RestartSec=10
StandardOutput=append:/var/log/origin.log
StandardError=append:/var/log/origin.log

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/origin

[Install]
WantedBy=multi-user.target
```

**Note:** ORIGIN is interactive (TUI). For headless operation, future HORIZON release will include CLI flags.

### Screen/Tmux Session (Recommended)

```bash
# Start detached session
tmux new-session -d -s origin "python3 ORIGIN.py"

# Attach later
tmux attach -t origin

# Detach: Ctrl+B, then D
```

---

## Docker Deployment

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copy application
COPY ORIGIN.py .

# Optional: install coincurve for speedup
RUN pip install --no-cache-dir coincurve

# Create non-root user
RUN useradd -m -u 1000 origin && chown -R origin:origin /app
USER origin

# Run
CMD ["python3", "ORIGIN.py"]
```

### Build & Run

```bash
# Build
docker build -t origin:latest .

# Run interactively
docker run -it --rm \
  -v $(pwd)/bruteaddress.txt:/app/bruteaddress.txt \
  -v $(pwd)/wallet_vault.json:/app/wallet_vault.json \
  -v $(pwd)/hunt_log.txt:/app/hunt_log.txt \
  origin:latest

# Run detached (with tmux inside)
docker run -d --name origin-hunt \
  -v $(pwd)/data:/app \
  origin:latest
```

### Docker Compose

```yaml
version: '3.8'
services:
  origin:
    build: .
    container_name: origin
    volumes:
      - ./data:/app
      - ./bruteaddress.txt:/app/bruteaddress.txt:ro
    stdin_open: true
    tty: true
    restart: unless-stopped
```

---

## Security Hardening

### 1. File Permissions

```bash
# Restrict vault access
chmod 600 wallet_vault.json
chown origin:origin wallet_vault.json

# Make script read-only
chmod 555 ORIGIN.py

# Protect hunt logs
chmod 600 hunt_log.txt
```

### 2. SELinux/AppArmor

```bash
# SELinux: Create custom policy
cat > origin.te <<EOF
module origin 1.0;

require {
    type user_t;
    class file { read write create };
}

allow user_t origin_exec_t:file { read execute };
EOF

# AppArmor: Create profile
cat > /etc/apparmor.d/origin <<EOF
/opt/origin/ORIGIN.py {
  /opt/origin/** rw,
  /usr/bin/python3 ix,
  deny network,
}
EOF
```

### 3. Audit Logging

```bash
# Log all vault access
auditctl -w /opt/origin/wallet_vault.json -p wa -k origin_vault

# Review logs
ausearch -k origin_vault
```

### 4. Memory Protection

```bash
# Clear swap before running sensitive operations
sudo swapoff -a

# Run with memory limits
systemd-run --scope -p MemoryMax=4G python3 ORIGIN.py
```

---

## Monitoring

### Hunt Progress Monitoring

```bash
# Watch hunt_log.txt in real-time
tail -f hunt_log.txt

# Check pause flag status
ls -la hunt_pause.flag 2>/dev/null && echo "PAUSED" || echo "RUNNING"

# Monitor CPU and memory
htop -p $(pgrep -f ORIGIN.py)
```

### Checkpoint Monitoring

```bash
# List checkpoints
ls -la hunt_checkpoint_*.json

# Check checkpoint content
python3 -m json.tool hunt_checkpoint_full.json
```

### Vault Monitoring

```bash
# Vault size
du -h wallet_vault.json

# Record count
python3 -c "import json; print(len(json.load(open('wallet_vault.json'))))"
```

---

## Backup & Recovery

### Vault Backup

```bash
# Automated backup script
cat > backup_vault.sh <<'EOF'
#!/bin/bash
VAULT="/opt/origin/wallet_vault.json"
BACKUP_DIR="/backup/origin"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"
cp "$VAULT" "$BACKUP_DIR/wallet_vault_$TIMESTAMP.json"

# Keep only last 10 backups
ls -t "$BACKUP_DIR"/wallet_vault_*.json | tail -n +11 | xargs rm -f
EOF

chmod +x backup_vault.sh
# Run via cron: 0 * * * * /opt/origin/backup_vault.sh
```

### Checkpoint Backup

```bash
# Backup checkpoints before major changes
tar czf checkpoints_backup_$(date +%Y%m%d).tar.gz hunt_checkpoint_*.json
```

### Recovery from Corrupted Vault

```bash
# If vault is corrupted, try JSON repair
python3 -c "
import json
with open('wallet_vault.json', 'r') as f:
    content = f.read()
    # Find last valid JSON array
    last_bracket = content.rfind(']')
    if last_bracket > 0:
        fixed = content[:last_bracket+1]
        data = json.loads(fixed)
        with open('wallet_vault_fixed.json', 'w') as out:
            json.dump(data, out, indent=2)
        print(f'Recovered {len(data)} records')
"
```

---

## Troubleshooting

### Issue: Self-tests fail on startup

```
CRYPTO SELF-TEST FAILED — Aborting for safety.
```

**Solutions:**
1. Run `[T]` for detailed failure information
2. Check Python version: `python3 --version` (need 3.8+)
3. Check for file corruption: `sha256sum ORIGIN.py`
4. Try pure Python: temporarily rename/remove `coincurve` if installed

### Issue: Address database won't load

```
bruteaddress.txt not found at: /path/to/bruteaddress.txt
```

**Solutions:**
1. Create the file: `touch bruteaddress.txt`
2. Check file permissions: `ls -la bruteaddress.txt`
3. Check file format: one address per line, ASCII only

### Issue: Very slow performance

**Solutions:**
1. Install coincurve: `pip install coincurve`
2. Reduce `addr_count` in hunt settings
3. Filter bruteaddress.txt to relevant address types
4. Check CPU throttling: `cat /proc/cpuinfo | grep MHz`

### Issue: Vault write failures

**Solutions:**
1. Check disk space: `df -h .`
2. Check file permissions: `ls -la wallet_vault.json`
3. Check for concurrent access (file locking should handle this)
4. Verify filesystem supports atomic rename

### Issue: Checkpoint mismatch on resume

```
Checkpoint mismatch — starting fresh.
```

**Solutions:**
1. Ensure cand_lists haven't changed
2. Check that passphrase, account, change, addr_count match
3. If intentional, delete old checkpoint: `rm hunt_checkpoint_*.json`

### Issue: Out of memory

```
MemoryError
```

**Solutions:**
1. Reduce address database size (filter to needed types)
2. Increase swap: `sudo swapon /swapfile`
3. Use a machine with more RAM
4. Process in smaller chunks (future HORIZON feature)

---

*End of Deployment Guide*
