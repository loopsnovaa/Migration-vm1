
#!/bin/bash
set -euo pipefail

SOURCE="counter-src"
DEST="counter-dst"
IMAGE="counter-migrated:latest"
REMOTE="maggie@192.168.88.13"

ARCHIVE="/tmp/counter-src.tar"
RUNNER="/tmp/counter_resume.py"

echo "===== CONTAINER MIGRATION STARTED ====="

# 1. Get the latest counter value from source logs
COUNT=$(sudo podman logs "$SOURCE" 2>&1 |
    sed -n 's/^Count: \([0-9][0-9]*\)$/\1/p' |
    tail -n 1)

if [[ -z "$COUNT" ]]; then
    echo "ERROR: Could not retrieve source counter value."
    exit 1
fi

echo "Source counter value: $COUNT"

# 2. Export source container filesystem
echo "Exporting container filesystem..."
sudo podman export "$SOURCE" -o "$ARCHIVE"
sudo chmod 644 "$ARCHIVE"

# 3. Create destination counter runner
cat > "$RUNNER" <<PYTHON
import time

count = $COUNT

print(f"Resuming from count: {count}", flush=True)

while True:
    count += 1
    print(f"Count: {count}", flush=True)
    time.sleep(1)
PYTHON

# 4. Transfer archive and runner to VM2
echo "Transferring files to VM2..."
scp "$ARCHIVE" "$REMOTE:/tmp/counter-src.tar"
scp "$RUNNER" "$REMOTE:/tmp/counter_resume.py"

# 5. Import image and create destination container
echo "Creating destination container on VM2..."

ssh -t "$REMOTE" "bash -s -- '$COUNT'" <<'REMOTE_SCRIPT'
set -e

COUNT="$1"
DEST="counter-dst"
IMAGE="counter-migrated:latest"

# Remove only the previous destination container
sudo podman rm -f "$DEST" 2>/dev/null || true

# Import transferred filesystem
sudo podman import /tmp/counter-src.tar "$IMAGE"

# Create destination container
sudo podman create --pull=never \
    --name "$DEST" \
    "$IMAGE" \
    python -u /tmp/counter_resume.py

# Copy counter runner into destination
sudo podman cp /tmp/counter_resume.py "$DEST:/tmp/counter_resume.py"

# Start destination
sudo podman start "$DEST"

echo "===== DESTINATION CONTAINER ====="
sudo podman ps -a --filter "name=$DEST"

echo "===== DESTINATION COUNTER ====="
sudo podman logs --tail 5 "$DEST"
REMOTE_SCRIPT

echo "===== MIGRATION FINISHED ====="
echo "Transferred counter value: $COUNT"
echo "Destination: VM2 / counter-dst"
