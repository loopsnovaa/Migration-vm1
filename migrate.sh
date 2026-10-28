
#!/usr/bin/env bash
set -Eeuo pipefail

# Source container on VM1
SOURCE="counter-src"
CHECKPOINT="/tmp/counter-checkpoint.tar.gz"

# Destination VM2
REMOTE_USER="maggie"
REMOTE_HOST="192.168.88.13"
REMOTE="${REMOTE_USER}@${REMOTE_HOST}"
DEST="counter-dst"
REMOTE_CHECKPOINT="/tmp/counter-checkpoint.tar.gz"

echo "=================================="
echo "   CROSS-VM MIGRATION STARTING"
echo "=================================="

echo
echo "[1/7] Checking SSH connectivity..."
ssh "$REMOTE" "hostname"

echo
echo "[2/7] Starting source container..."
STATUS=$(sudo podman inspect \
    --format '{{.State.Status}}' "$SOURCE")

if [ "$STATUS" != "running" ]; then
    sudo podman start "$SOURCE"
fi

echo
echo "[3/7] Letting counter-src run for 10 seconds..."
sleep 10

echo "Source container logs:"
sudo podman logs --tail 10 "$SOURCE"

echo
echo "[4/7] Checkpointing source container..."
sudo podman container checkpoint \
    --export "$CHECKPOINT" "$SOURCE"

sudo chmod 644 "$CHECKPOINT"

echo "Checkpoint archive:"
ls -lh "$CHECKPOINT"

echo
echo "[5/7] Transferring checkpoint to VM2..."
scp "$CHECKPOINT" "${REMOTE}:${REMOTE_CHECKPOINT}"

echo
echo "[6/7] Removing old destination and restoring on VM2..."

# -t allows remote sudo to prompt for VM2's password if required.
ssh -t "$REMOTE" \
    "if sudo podman container exists '$DEST'; then
        sudo podman rm -f '$DEST'
    fi"

ssh -t "$REMOTE" \
    "sudo podman container restore \
        -i='$REMOTE_CHECKPOINT' \
        --name='$DEST'"

echo
echo "[7/7] Verifying destination on VM2..."

ssh -t "$REMOTE" \
    "sudo podman ps -a &&
     echo 'Destination status:' &&
     sudo podman inspect --format '{{.State.Status}}' '$DEST' &&
     echo 'Destination logs:' &&
     sudo podman logs --tail 10 '$DEST'"

echo
echo "=================================="
echo "   MIGRATION SCRIPT FINISHED"
echo "=================================="
echo "Watch the destination counter using:"
echo "ssh $REMOTE"
echo "sudo podman logs -f $DEST"
