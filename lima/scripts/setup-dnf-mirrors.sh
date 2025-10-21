#!/bin/bash
# Configure DNF to use known good HTTP mirrors and avoid slow/timeout-prone mirrors

set -eu

echo "Configuring DNF with known good HTTP mirrors..."

# DNF configuration for better mirror selection
cat >> /etc/dnf/dnf.conf <<'EOF'

# Mirror selection optimization
fastestmirror=False
ip_resolve=4
timeout=10
retries=3
skip_if_unavailable=True
EOF

# Use kernel.org global edge mirrors (CDN with geographic distribution)
# Allow override via FEDORA_MIRROR_REGION environment variable
# Valid regions: na (North America), eu (Europe), ap (Asia-Pacific)
# Default: mirrors.kernel.org (auto-redirects to nearest edge)

if [ -n "${FEDORA_MIRROR_REGION:-}" ]; then
    case "${FEDORA_MIRROR_REGION}" in
        na|eu|ap)
            MIRROR_BASE="http://${FEDORA_MIRROR_REGION}.edge.kernel.org/fedora"
            echo "Using regional mirror: ${MIRROR_BASE}"
            ;;
        *)
            echo "Warning: Invalid FEDORA_MIRROR_REGION '${FEDORA_MIRROR_REGION}'"
            echo "Valid options: na, eu, ap. Using auto-redirect instead."
            MIRROR_BASE="http://mirrors.kernel.org/fedora"
            ;;
    esac
else
    # Default: let kernel.org redirect to nearest edge mirror
    MIRROR_BASE="http://mirrors.kernel.org/fedora"
    echo "Using kernel.org auto-redirect (detects nearest: na/eu/ap edge)"
fi

# Configure fedora.repo
if [ -f /etc/yum.repos.d/fedora.repo ]; then
    echo "Configuring fedora.repo with HTTP mirrors..."

    # Backup original
    cp /etc/yum.repos.d/fedora.repo /etc/yum.repos.d/fedora.repo.orig

    # Disable metalink and use baseurl with known good mirrors
    sed -i 's/^metalink=/#metalink=/g' /etc/yum.repos.d/fedora.repo
    sed -i 's/^#baseurl=/baseurl=/g' /etc/yum.repos.d/fedora.repo

    # Replace with configured kernel.org mirror
    sed -i "s|download.example/pub/fedora/linux|${MIRROR_BASE#http://}|g" /etc/yum.repos.d/fedora.repo

    # Ensure HTTP (not HTTPS)
    sed -i 's|baseurl=https://|baseurl=http://|g' /etc/yum.repos.d/fedora.repo

    echo "✓ fedora.repo configured"
fi

# Configure fedora-updates.repo
if [ -f /etc/yum.repos.d/fedora-updates.repo ]; then
    echo "Configuring fedora-updates.repo with HTTP mirrors..."

    # Backup original
    cp /etc/yum.repos.d/fedora-updates.repo /etc/yum.repos.d/fedora-updates.repo.orig

    # Disable metalink and use baseurl
    sed -i 's/^metalink=/#metalink=/g' /etc/yum.repos.d/fedora-updates.repo
    sed -i 's/^#baseurl=/baseurl=/g' /etc/yum.repos.d/fedora-updates.repo

    # Replace with configured kernel.org mirror
    sed -i "s|download.example/pub/fedora/linux|${MIRROR_BASE#http://}|g" /etc/yum.repos.d/fedora-updates.repo

    # Ensure HTTP (not HTTPS)
    sed -i 's|baseurl=https://|baseurl=http://|g' /etc/yum.repos.d/fedora-updates.repo

    echo "✓ fedora-updates.repo configured"
fi

# Clean DNF cache to ensure new configuration is used
dnf clean all 2>/dev/null || true

echo "✓ DNF configured to use HTTP mirrors only (kernel.org primary)"
echo "  This avoids slow international mirrors and HTTPS timeout issues"
