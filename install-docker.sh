#!/bin/bash
# Docker Engine Installation Script for Debian 12 (Bookworm)
# This replaces Docker Desktop functionality on a Linux VPS

set -e

echo "🐳 Docker Engine Installation for WDFWatch VPS"
echo "=============================================="
echo ""

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then 
    echo "This script needs sudo privileges. Re-running with sudo..."
    exec sudo "$0" "$@"
fi

echo "📦 Step 1: Updating package index..."
apt-get update

echo "📦 Step 2: Installing prerequisites..."
apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

echo "🔑 Step 3: Adding Docker's official GPG key..."
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo "📝 Step 4: Setting up Docker repository..."
echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

echo "📦 Step 5: Installing Docker Engine..."
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo "🔧 Step 6: Starting Docker service..."
systemctl start docker
systemctl enable docker

echo "👤 Step 7: Adding current user to docker group..."
usermod -aG docker debian || true

echo "✅ Step 8: Verifying installation..."
docker --version
docker compose version

echo ""
echo "=============================================="
echo "✅ Docker Engine Installation Complete!"
echo "=============================================="
echo ""
echo "⚠️  IMPORTANT: You need to log out and back in for group changes to take effect."
echo "   Or run: newgrp docker"
echo ""
echo "📋 Installed components:"
echo "   - Docker Engine (replaces Docker Desktop)"
echo "   - Docker Compose v2 (as docker compose plugin)"
echo "   - Docker Buildx (for multi-platform builds)"
echo ""
echo "🎯 Next steps:"
echo "   1. Run: newgrp docker"
echo "   2. Then run: ./setup-wdfwatch-env.sh"
echo ""