#!/bin/bash
# Configure user environment for builds

set -eu

PROXY_HOST="host.lima.internal"
PROXY_PORT="3128"

# Set up user containers configuration
mkdir -p ~/.config/containers ~/.local/share/containers/storage
echo 'TMPDIR="$HOME/.local/share/containers/tmp"' >> ~/.bashrc

# Configure proxy environment for user session
if timeout 2 bash -c "cat < /dev/null > /dev/tcp/${PROXY_HOST}/${PROXY_PORT}" 2>/dev/null; then
    cat >> ~/.bashrc << 'EOF'

# Build Proxy Configuration
export http_proxy="http://host.lima.internal:3128"
export https_proxy="http://host.lima.internal:3128"
export HTTP_PROXY="http://host.lima.internal:3128"
export HTTPS_PROXY="http://host.lima.internal:3128"
export no_proxy="localhost,127.0.0.1,host.lima.internal"
export NO_PROXY="localhost,127.0.0.1,host.lima.internal"
EOF
    echo "✓ User proxy environment configured"
fi
