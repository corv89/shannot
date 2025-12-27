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

# Setup shannot runtime (downloads PyPy stdlib and sandbox binary)
echo -e "${BOLD}Setting up shannot runtime...${NC}"
uv run shannot setup runtime
echo -e "${GREEN}✓ Shannot runtime configured${NC}\n"

# Verify installation
echo -e "${BOLD}Verifying installation...${NC}"
uv run shannot status
echo ""

# Add venv activation and welcome message to shell rc
{
  echo 'source /workspaces/shannot/.venv/bin/activate'
  echo 'echo -e "\033[1mShannot dev environment ready.\033[0m Run \033[0;34mshannot --help\033[0m for commands."'
} >> ~/.bashrc

{
  echo 'source /workspaces/shannot/.venv/bin/activate'
  echo 'echo -e "\033[1mShannot dev environment ready.\033[0m Run \033[0;34mshannot --help\033[0m for commands."'
} >> ~/.zshrc
