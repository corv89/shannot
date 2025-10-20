#!/bin/bash
# Post-creation setup script for Shannot development container

set -e

BOLD='\033[1m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BOLD}${BLUE}Setting up Shannot development environment...${NC}\n"

# Install bubblewrap (critical dependency)
echo -e "${BOLD}Installing bubblewrap...${NC}"
sudo apt-get update -qq
sudo apt-get install -y bubblewrap
echo -e "${GREEN}✓ bubblewrap installed${NC}\n"

# Install Python development dependencies
echo -e "${BOLD}Installing Python dependencies...${NC}"
pip install --upgrade pip
pip install -e ".[dev]"
echo -e "${GREEN}✓ Python dependencies installed${NC}\n"

# Create config directory and install default profile
echo -e "${BOLD}Setting up shannot configuration...${NC}"
mkdir -p ~/.config/shannot
if [ ! -f ~/.config/shannot/profile.json ]; then
    cp profiles/minimal.json ~/.config/shannot/profile.json
    echo -e "${GREEN}✓ Default profile installed to ~/.config/shannot/profile.json${NC}"
else
    echo -e "${GREEN}✓ Profile already exists${NC}"
fi
echo ""

# Verify installation
echo -e "${BOLD}Verifying shannot installation...${NC}"
if shannot verify --allowed-command ls / 2>&1 | grep -q "Verifying"; then
    echo -e "${GREEN}✓ Shannot sandbox is working!${NC}\n"
else
    echo -e "${BLUE}ℹ Sandbox verification completed${NC}\n"
fi

# Display welcome message
echo -e "${BOLD}${GREEN}🎉 Development environment ready!${NC}\n"
echo -e "${BOLD}Quick start commands:${NC}"
echo -e "  ${BLUE}shannot run ls /${NC}              # Run ls / in sandbox"
echo -e "  ${BLUE}shannot verify${NC}                # Verify sandbox works"
echo -e "  ${BLUE}shannot export${NC}                # Export profile config"
echo -e ""
echo -e "${BOLD}Development commands:${NC}"
echo -e "  ${BLUE}pytest tests/${NC}                 # Run test suite"
echo -e "  ${BLUE}pytest tests/ -v --cov${NC}        # Run tests with coverage"
echo -e "  ${BLUE}ruff check .${NC}                  # Lint code"
echo -e "  ${BLUE}ruff format .${NC}                 # Format code"
echo -e "  ${BLUE}basedpyright${NC}                  # Type check"
echo -e ""
echo -e "${BOLD}Available profiles:${NC}"
echo -e "  ${BLUE}profiles/minimal.json${NC}         # Basic commands (default)"
echo -e "  ${BLUE}profiles/readonly.json${NC}        # Extended read-only access"
echo -e "  ${BLUE}profiles/diagnostics.json${NC}     # System diagnostics"
echo -e ""
echo -e "Happy coding! 🚀\n"
