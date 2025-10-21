#!/bin/bash
# Configure container registry mirrors

set -eu

mkdir -p /etc/containers/registries.conf.d

cat > /etc/containers/registries.conf.d/000-mirrors.conf << 'EOF'
unqualified-search-registries = ["docker.io", "quay.io", "registry.fedoraproject.org"]

[[registry]]
prefix = "docker.io"
location = "docker.io"

[[registry.mirror]]
location = "host.lima.internal:5100"
insecure = true

[[registry]]
prefix = "quay.io"
location = "quay.io"

[[registry.mirror]]
location = "host.lima.internal:5101"
insecure = true

[[registry]]
prefix = "ghcr.io"
location = "ghcr.io"

[[registry.mirror]]
location = "host.lima.internal:5102"
insecure = true
EOF

echo "✓ Container registry mirrors configured"
