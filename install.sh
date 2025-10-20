#!/bin/bash
# Installation script for shannot sandbox
# Simple deployment for remote systems

set -e

BOLD='\033[1m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BOLD}Shannot Sandbox Installer${NC}"
echo "======================================"
echo

# Check for bubblewrap
echo -n "Checking for bubblewrap... "
if command -v bwrap &> /dev/null; then
    BWRAP_VERSION=$(bwrap --version | head -n1)
    echo -e "${GREEN}✓${NC} Found: $BWRAP_VERSION"
else
    echo -e "${RED}✗${NC} Not found"
    echo
    echo "Error: bubblewrap (bwrap) is required but not installed."
    echo
    echo "Install with:"
    echo "  ${BOLD}Fedora/RHEL:${NC}     sudo dnf install bubblewrap"
    echo "  ${BOLD}Debian/Ubuntu:${NC}   sudo apt install bubblewrap"
    echo "  ${BOLD}Arch Linux:${NC}      sudo pacman -S bubblewrap"
    echo "  ${BOLD}openSUSE:${NC}        sudo zypper install bubblewrap"
    exit 1
fi

# Check Python version
echo -n "Checking Python version... "
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f1)
    PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f2)

    if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 9 ]; then
        echo -e "${GREEN}✓${NC} Python $PYTHON_VERSION"
    else
        echo -e "${YELLOW}!${NC} Python $PYTHON_VERSION (3.9+ required)"
        echo -e "  ${YELLOW}Warning:${NC} shannot requires Python 3.9 or newer"
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
else
    echo -e "${RED}✗${NC} Python 3 not found"
    exit 1
fi

# Install shannot
echo
echo "Installing shannot..."
if [ -w "$(python3 -m site --user-site)" ] || [ -w "$(python3 -c 'import site; print(site.getsitepackages()[0])')" ]; then
    python3 -m pip install --user . || {
        echo -e "${RED}Installation failed${NC}"
        exit 1
    }
else
    echo "Note: May require sudo for system-wide installation"
    sudo python3 -m pip install . || {
        echo -e "${RED}Installation failed${NC}"
        exit 1
    }
fi

# Create config directory
echo "Creating configuration directory..."
mkdir -p ~/.config/shannot

# Copy example profile if it doesn't exist
if [ ! -f ~/.config/shannot/profile.json ]; then
    echo "Installing default profile..."
    cp profiles/minimal.json ~/.config/shannot/profile.json
    echo -e "  ${GREEN}→${NC} ~/.config/shannot/profile.json"
    echo -e "  ${GREEN}ℹ${NC}  Other profiles available in profiles/ directory"
else
    echo -e "  ${YELLOW}!${NC} Profile already exists at ~/.config/shannot/profile.json"
    echo "    (not overwriting)"
fi

# Verify installation
echo
echo "Verifying installation..."
if command -v shannot &> /dev/null; then
    echo -e "${GREEN}✓${NC} shannot command is available"

    # Run verification test
    echo
    echo "Running sandbox verification..."
    if shannot verify --allowed-command ls / 2>&1 | grep -q "Verifying"; then
        echo -e "${GREEN}✓${NC} Sandbox is working correctly!"
    else
        echo -e "${YELLOW}!${NC} Verification had issues (check with: shannot verify --verbose)"
    fi
else
    echo -e "${RED}✗${NC} shannot command not found in PATH"
    echo "You may need to add $(python3 -m site --user-base)/bin to your PATH"
    exit 1
fi

echo
echo -e "${GREEN}${BOLD}Installation complete!${NC}"
echo
echo "Quick start:"
echo "  ${BOLD}shannot run ls /${NC}              # Run ls / in sandbox"
echo "  ${BOLD}shannot verify${NC}                # Verify sandbox works"
echo "  ${BOLD}shannot export${NC}                # Export profile config"
echo "  ${BOLD}shannot --help${NC}                # Show all options"
echo
echo "Configuration:"
echo "  Profile: ~/.config/shannot/profile.json"
echo
echo "Documentation: https://github.com/corv89/shannot"
