#!/bin/bash
# Setup systemd service and timer for automatic OAuth token refresh

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SERVICE_FILE="$SCRIPT_DIR/wdfwatch-token-refresh.service"
TIMER_FILE="$SCRIPT_DIR/wdfwatch-token-refresh.timer"

echo "=========================================="
echo "WDFWatch Token Refresh SystemD Setup"
echo "=========================================="

# Check if running as root or with sudo
if [[ $EUID -eq 0 ]]; then
   echo "✅ Running with root privileges"
else
   echo "❌ This script must be run with sudo"
   echo "   Run: sudo bash $0"
   exit 1
fi

# Copy service files to systemd directory
echo ""
echo "Installing systemd service files..."
cp "$SERVICE_FILE" /etc/systemd/system/
cp "$TIMER_FILE" /etc/systemd/system/

# Reload systemd daemon
echo "Reloading systemd daemon..."
systemctl daemon-reload

# Enable and start the timer
echo "Enabling token refresh timer..."
systemctl enable wdfwatch-token-refresh.timer

echo "Starting token refresh timer..."
systemctl start wdfwatch-token-refresh.timer

# Check status
echo ""
echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo ""
echo "Service status:"
systemctl status wdfwatch-token-refresh.timer --no-pager || true
echo ""
echo "Next scheduled run:"
systemctl list-timers wdfwatch-token-refresh.timer --no-pager
echo ""
echo "Useful commands:"
echo "  View logs:         sudo journalctl -u wdfwatch-token-refresh.service -f"
echo "  Run manually:      sudo systemctl start wdfwatch-token-refresh.service"
echo "  Check timer:       sudo systemctl status wdfwatch-token-refresh.timer"
echo "  Disable timer:     sudo systemctl stop wdfwatch-token-refresh.timer"
echo ""
echo "✅ Token refresh will now run automatically every 30 minutes"