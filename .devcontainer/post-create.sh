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

# Add venv activation to shell rc so shannot is available directly
echo 'source /workspaces/shannot/.venv/bin/activate' >> ~/.bashrc
echo 'source /workspaces/shannot/.venv/bin/activate' >> ~/.zshrc

# Display welcome message
echo -e "${BOLD}${GREEN}Development environment ready!${NC}\n"

echo -e "${BOLD}What is Shannot?${NC}"
echo -e "  Shannot runs Python scripts in a secure sandbox. Scripts can request"
echo -e "  shell commands and file writes, but nothing executes until you approve."
echo -e ""

echo -e "${BOLD}Try it out:${NC}"
echo -e "  1. Create a test script:"
echo -e "     ${BLUE}echo 'import os; os.system(\"echo Hello from sandbox\")' > test.py${NC}"
echo -e ""
echo -e "  2. Run it in the sandbox:"
echo -e "     ${BLUE}shannot run test.py${NC}"
echo -e ""
echo -e "  3. Review and approve the queued command:"
echo -e "     ${BLUE}shannot approve${NC}"
echo -e ""

echo -e "${BOLD}Other commands:${NC}"
echo -e "  ${BLUE}shannot status${NC}     Check runtime status"
echo -e "  ${BLUE}shannot --help${NC}     Show all commands"
echo -e ""

echo -e "${BOLD}Development:${NC}"
echo -e "  ${BLUE}make test${NC}          Run all tests"
echo -e "  ${BLUE}make lint${NC}          Check code style"
echo -e "  ${BLUE}make format${NC}        Auto-format code"
echo -e ""

echo -e "See README.md for full documentation. Happy coding!\n"
