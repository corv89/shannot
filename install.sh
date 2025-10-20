#!/bin/bash
# Installation script for shannot sandbox
# Simple deployment for remote systems

set -e

BOLD='\033[1m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse command line arguments
NON_INTERACTIVE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -y|--yes)
            NON_INTERACTIVE=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo
            echo "Options:"
            echo "  -y, --yes      Non-interactive mode: auto-install uv if needed,"
            echo "                 accept all prompts (recommended for automation)"
            echo "  -h, --help     Show this help message"
            echo
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Run '$0 --help' for usage information"
            exit 1
            ;;
    esac
done

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

# Check Python version (relaxed if uv is available or will be installed)
echo -n "Checking Python version... "
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f1)
    PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f2)

    if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 9 ]; then
        echo -e "${GREEN}✓${NC} Python $PYTHON_VERSION"
    else
        echo -e "${YELLOW}!${NC} Python $PYTHON_VERSION (3.9+ recommended)"
        if command -v uv &> /dev/null || [ "$NON_INTERACTIVE" = true ]; then
            echo -e "  ${GREEN}Note:${NC} uv will manage Python version automatically"
        else
            echo -e "  ${YELLOW}Warning:${NC} shannot requires Python 3.9 or newer for pip installation"
            if [ "$NON_INTERACTIVE" = false ]; then
                read -p "Continue anyway? (y/N) " -n 1 -r
                echo
                if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                    exit 1
                fi
            fi
        fi
    fi
else
    if command -v uv &> /dev/null || [ "$NON_INTERACTIVE" = true ]; then
        echo -e "${YELLOW}!${NC} Python 3 not found (uv will manage Python)"
    else
        echo -e "${RED}✗${NC} Python 3 not found"
        exit 1
    fi
fi

# Install shannot
echo
echo "Installing shannot..."

# Detect if we're installing from local source or remote
if [ -f "pyproject.toml" ] && grep -q 'name = "shannot"' pyproject.toml 2>/dev/null; then
    INSTALL_SOURCE="local"
    echo "Detected local source directory"
else
    INSTALL_SOURCE="remote"
    echo "Installing from PyPI"
fi

# Check if uv is available
if command -v uv &> /dev/null; then
    echo "Using uv for installation..."
    if [ "$INSTALL_SOURCE" = "local" ]; then
        uv tool install --from . shannot || {
            echo -e "${RED}Installation with uv failed${NC}"
            exit 1
        }
    else
        uv tool install shannot || {
            echo -e "${RED}Installation with uv failed${NC}"
            exit 1
        }
    fi
# Offer to install uv if not present
elif ! command -v pipx &> /dev/null; then
    SHOULD_INSTALL_UV=false

    if [ "$NON_INTERACTIVE" = true ]; then
        SHOULD_INSTALL_UV=true
        echo "Auto-installing uv (non-interactive mode)..."
    else
        echo -e "${YELLOW}Recommended:${NC} Install shannot using 'uv' (fast, modern Python package installer)"
        echo
        echo "uv automatically handles:"
        echo "  • Isolated environments (no system Python conflicts)"
        echo "  • Fast, reliable installation"
        echo "  • Automatic PATH configuration"
        echo
        read -p "Install uv and use it to install shannot? [Y/n] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
            SHOULD_INSTALL_UV=true
        fi
    fi

    if [ "$SHOULD_INSTALL_UV" = true ]; then
        echo "Installing uv..."
        if curl -LsSf https://astral.sh/uv/install.sh | sh; then
            # Source the uv environment to make it available in current shell
            export PATH="$HOME/.local/bin:$PATH"

            # Verify uv is now available
            if command -v uv &> /dev/null; then
                echo -e "${GREEN}✓${NC} uv installed successfully"
                echo
                echo "Installing shannot with uv..."
                if [ "$INSTALL_SOURCE" = "local" ]; then
                    uv tool install --from . shannot || {
                        echo -e "${RED}Installation with uv failed${NC}"
                        exit 1
                    }
                else
                    uv tool install shannot || {
                        echo -e "${RED}Installation with uv failed${NC}"
                        exit 1
                    }
                fi
            else
                echo -e "${YELLOW}Note:${NC} uv installed but not yet in PATH"
                echo "  Please restart your shell or run: source ~/.bashrc (or ~/.zshrc)"
                echo
                echo "Falling back to pip for this session..."
                INSTALL_METHOD="fallback"
            fi
        else
            echo -e "${YELLOW}uv installation failed, falling back to pip${NC}"
            INSTALL_METHOD="fallback"
        fi
    else
        echo "Skipping uv installation"
        INSTALL_METHOD="fallback"
    fi
fi

# Fall back to pipx if available and uv installation was skipped/failed
if [ "$INSTALL_METHOD" = "fallback" ] && command -v pipx &> /dev/null; then
    echo "Using pipx for installation..."
    if [ "$INSTALL_SOURCE" = "local" ]; then
        pipx install . || {
            echo -e "${RED}Installation with pipx failed${NC}"
            exit 1
        }
    else
        pipx install shannot || {
            echo -e "${RED}Installation with pipx failed${NC}"
            exit 1
        }
    fi
# Use traditional pip as last resort
elif [ "$INSTALL_METHOD" = "fallback" ]; then
    echo -e "${YELLOW}Note:${NC} Using pip installation..."
    echo "  For better experience, install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo

    # Determine pip install target
    if [ "$INSTALL_SOURCE" = "local" ]; then
        PIP_TARGET="."
    else
        PIP_TARGET="shannot"
    fi

    # Try pip install and check for PEP 668 error
    if python3 -m pip install --user "$PIP_TARGET" 2>&1 | grep -q "externally-managed-environment"; then
        echo -e "${YELLOW}Error:${NC} System Python is externally managed (PEP 668)"
        echo

        if [ "$NON_INTERACTIVE" = true ]; then
            echo "Non-interactive mode: using --break-system-packages"
            python3 -m pip install --user --break-system-packages "$PIP_TARGET" || {
                echo -e "${RED}Installation failed${NC}"
                exit 1
            }
        else
            echo "Options:"
            echo "  1. Install uv:   curl -LsSf https://astral.sh/uv/install.sh | sh"
            echo "  2. Install pipx: sudo apt install pipx  (or equivalent for your distro)"
            echo "  3. Use --break-system-packages (not recommended)"
            echo
            read -p "Try installing with --break-system-packages? [y/N] " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                python3 -m pip install --user --break-system-packages "$PIP_TARGET" || {
                    echo -e "${RED}Installation failed${NC}"
                    exit 1
                }
            else
                echo -e "${RED}Installation cancelled${NC}"
                echo "Please install uv or pipx and try again"
                exit 1
            fi
        fi
    fi
fi

# Create config directory
echo "Creating configuration directory..."
mkdir -p ~/.config/shannot

# Copy example profile if it doesn't exist
if [ ! -f ~/.config/shannot/profile.json ]; then
    echo "Installing default profile..."
    if [ "$INSTALL_SOURCE" = "local" ] && [ -f "profiles/minimal.json" ]; then
        cp profiles/minimal.json ~/.config/shannot/profile.json
        echo -e "  ${GREEN}→${NC} ~/.config/shannot/profile.json"
        echo -e "  ${GREEN}ℹ${NC}  Other profiles available in profiles/ directory"
    else
        # For remote installations, fetch from GitHub (required)
        PROFILE_URL="https://raw.githubusercontent.com/corv89/shannot/main/profiles/minimal.json"
        DOWNLOAD_SUCCESS=false

        if command -v curl &> /dev/null; then
            if curl -fsSL "$PROFILE_URL" -o ~/.config/shannot/profile.json; then
                DOWNLOAD_SUCCESS=true
                echo -e "  ${GREEN}→${NC} ~/.config/shannot/profile.json (downloaded from GitHub)"
            fi
        elif command -v wget &> /dev/null; then
            if wget -qO ~/.config/shannot/profile.json "$PROFILE_URL"; then
                DOWNLOAD_SUCCESS=true
                echo -e "  ${GREEN}→${NC} ~/.config/shannot/profile.json (downloaded from GitHub)"
            fi
        else
            echo -e "  ${RED}✗${NC} Neither curl nor wget available"
        fi

        if [ "$DOWNLOAD_SUCCESS" = false ]; then
            echo -e "  ${RED}✗${NC} Failed to download profile from GitHub"
            echo
            echo "To complete installation manually:"
            echo "  1. Download a profile from: https://github.com/corv89/shannot/tree/main/profiles"
            echo "  2. Save it to: ~/.config/shannot/profile.json"
            echo
            echo "Or clone the repository to use the local installation method."
            exit 1
        fi
        echo -e "  ${GREEN}ℹ${NC}  See https://github.com/corv89/shannot/tree/main/profiles for more profiles"
    fi
else
    echo -e "  ${YELLOW}!${NC} Profile already exists at ~/.config/shannot/profile.json"
    echo "    (not overwriting)"
fi

# Verify installation
echo
echo "Verifying installation..."

# Add common tool installation paths to PATH for verification
export PATH="$HOME/.local/bin:$PATH"

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
    echo
    echo "Add to your PATH by adding this to ~/.bashrc or ~/.zshrc:"
    echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo
    echo "Then restart your shell or run: source ~/.bashrc (or ~/.zshrc)"
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
