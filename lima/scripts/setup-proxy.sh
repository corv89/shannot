#!/bin/bash
# Configure caching proxy for DNF and container registries

set -eu

PROXY_HOST="host.lima.internal"
PROXY_PORT="3128"

# Check if proxy is available
if ! timeout 2 bash -c "cat < /dev/null > /dev/tcp/${PROXY_HOST}/${PROXY_PORT}" 2>/dev/null; then
    echo "⚠ No caching proxy detected, using direct connection"
    echo "  Run './proxy.py start' on host for faster builds"
    exit 0
fi

echo "✓ Caching proxy detected at ${PROXY_HOST}:${PROXY_PORT}"

# Configure DNF proxy (mirrors already configured by setup-dnf-mirrors.sh)
echo "proxy=http://${PROXY_HOST}:${PROXY_PORT}" >> /etc/dnf/dnf.conf
echo "sslverify=True" >> /etc/dnf/dnf.conf

# Export proxy environment variables
export http_proxy="http://${PROXY_HOST}:${PROXY_PORT}"
export https_proxy="http://${PROXY_HOST}:${PROXY_PORT}"
export HTTP_PROXY="http://${PROXY_HOST}:${PROXY_PORT}"
export HTTPS_PROXY="http://${PROXY_HOST}:${PROXY_PORT}"
export no_proxy="localhost,127.0.0.1,host.lima.internal"
export NO_PROXY="localhost,127.0.0.1,host.lima.internal"

echo "✓ Proxy configured with HTTP-only mirrors for full caching"
