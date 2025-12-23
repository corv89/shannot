#!/bin/bash
# Post-creation setup script for Shannot development container

set -e

BOLD='\033[1m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BOLD}${BLUE}Setting up Shannot development environment...${NC}\n"

# Install uv (modern Python package manager)
echo -e "${BOLD}Installing uv...${NC}"
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
echo -e "${GREEN}✓ uv installed${NC}\n"

# Install Python dependencies
echo -e "${BOLD}Installing Python dependencies...${NC}"
uv sync --dev
echo -e "${GREEN}✓ Python dependencies installed${NC}\n"

# Setup shannot runtime (downloads PyPy stdlib)
echo -e "${BOLD}Setting up shannot runtime...${NC}"
uv run shannot setup
echo -e "${GREEN}✓ Shannot runtime configured${NC}\n"

# Create config directory
echo -e "${BOLD}Setting up shannot configuration...${NC}"
mkdir -p ~/.config/shannot
echo -e "${GREEN}✓ Config directory created${NC}\n"

# Display welcome message
echo -e "${BOLD}${GREEN}Development environment ready!${NC}\n"
echo -e "${BOLD}Quick start commands:${NC}"
echo -e "  ${BLUE}uv run shannot run script.py${NC}    # Run script in sandbox"
echo -e "  ${BLUE}uv run shannot status${NC}           # Check runtime status"
echo -e ""
echo -e "${BOLD}Development commands:${NC}"
echo -e "  ${BLUE}make test${NC}                       # Run all tests"
echo -e "  ${BLUE}make lint${NC}                       # Lint code"
echo -e "  ${BLUE}make format${NC}                     # Format code"
echo -e "  ${BLUE}make type-check${NC}                 # Type check"
echo -e ""
echo -e "Happy coding!\n"
