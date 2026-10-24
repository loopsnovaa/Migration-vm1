#!/usr/bin/env bash
set -Eeuo pipefail

SOURCE="counter-src"
DEST="counter-dst"
CHECKPOINT="/tmp/counter-checkpoint.tar.gz"

echo "=================================="
echo "   CONTAINER MIGRATION STARTING"
echo "=================================="

echo
echo "[1/6] Checking existing containers..."
sudo podman ps -a

echo
echo "[2/6] Starting source container..."
if [ "$(sudo podman inspect --format '{{.State.Status}}' "$SOURCE")" != "running" ]; then
    sudo podman start "$SOURCE"
fi

echo
echo "Source logs:"
sudo podman logs "$SOURCE"

echo
echo "[3/6] Removing existing destination, if present..."
if sudo podman container exists "$DEST"; then
    sudo podman rm -f "$DEST"
fi

echo
echo "[4/6] Checkpointing source and exporting state..."
sudo podman container checkpoint \
    --export "$CHECKPOINT" "$SOURCE"

echo
echo "Checkpoint archive:"
ls -lh "$CHECKPOINT"

echo
echo "[5/6] Restoring destination..."
sudo podman container restore \
    -i="$CHECKPOINT" --name="$DEST"

echo
echo "[6/6] Verifying migration..."
sudo podman ps -a

echo
echo "Destination status:"
sudo podman inspect --format '{{.State.Status}}' "$DEST"

echo
echo "Destination counter logs:"
sudo podman logs "$DEST"

echo
echo "=================================="
echo "   MIGRATION SCRIPT FINISHED"
echo "=================================="
echo "To watch the destination counter live, run:"
echo "sudo podman logs -f $DEST"
