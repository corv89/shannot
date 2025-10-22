# Shannot Documentation

Complete documentation for Shannot - read-only sandboxing for Linux.

## Getting Started

New to Shannot? Start here:

1. **[Installation Guide](installation.md)** - Install Shannot on any platform
2. **[Usage Guide](usage.md)** - Learn basic commands and workflows
3. **[Profile Configuration](profiles.md)** - Configure sandbox behavior

## Documentation Index

### Core Documentation

**[Installation Guide](installation.md)**
- Client installation (macOS, Linux, Windows)
- Target installation (Linux only - bubblewrap)
- Optional dependencies
- Post-installation setup

**[Usage Guide](usage.md)**
- Command-line interface
- Basic commands
- Profile selection
- Common use cases

**[Profile Configuration](profiles.md)**
- Profile structure and fields
- Creating custom profiles
- Example profiles
- Best practices

### Advanced Features

**[Configuration Guide](configuration.md)**
- Remote execution via SSH
- Multiple executors
- TOML configuration
- Ansible deployment

**[Deployment Guide](deployment.md)**
- Production deployment
- Ansible playbooks
- SSH integration
- Team configuration

**[API Reference](api.md)**
- Python API
- SandboxManager class
- ProcessResult handling
- Integration examples

### Integrations

**[MCP Integration](mcp.md)**
- Claude Desktop setup
- Available tools
- Security considerations
- Troubleshooting

**[Seccomp Filters](seccomp.md)** *(Optional)*
- Creating BPF filters
- Adding to profiles
- Testing filters

### Development

**[Testing Guide](testing.md)**
- Running tests
- Writing tests
- Test categories
- Coverage reports

**[Troubleshooting](troubleshooting.md)**
- Common issues
- Permission problems
- Environment-specific fixes

## Quick Links

### By Use Case

**Want to give Claude safe system access?**
→ [MCP Integration Guide](mcp.md)

**Need to monitor remote systems?**
→ [Configuration Guide](configuration.md) + [Deployment Guide](deployment.md)

**Building automation tools?**
→ [API Reference](api.md)

**Customizing sandbox behavior?**
→ [Profile Configuration](profiles.md)

**Having issues?**
→ [Troubleshooting Guide](troubleshooting.md)

### By Platform

**macOS/Windows (Client)**
1. [Install Shannot](installation.md#client-installation-any-platform)
2. [Configure remote targets](configuration.md#quick-start)
3. [Set up Claude Desktop](mcp.md#quick-start-5-minutes)

**Linux (Target)**
1. [Install bubblewrap](installation.md#target-installation-linux-only)
2. [Choose a profile](profiles.md#complete-example-profiles)
3. [Run commands](usage.md#quick-start)

**Production Deployment**
1. [Ansible playbook](deployment.md#ansible)
2. [SSH setup](deployment.md#ssh-integration)
3. [Security best practices](deployment.md#security-considerations)

## Documentation Standards

All Shannot documentation follows these principles:

- **Clarity first** - Simple language, clear examples
- **Quick starts** - Get users running fast
- **Complete coverage** - Every feature documented
- **Real examples** - Actual commands that work
- **Platform aware** - Clear about OS requirements

## Contributing to Docs

Found an issue or want to improve the documentation?

1. Check existing [GitHub issues](https://github.com/corv89/shannot/issues)
2. Submit a pull request with improvements
3. Follow the existing documentation style

See [CONTRIBUTING.md](../CONTRIBUTING.md) for details.

## Getting Help

- **Bug reports**: [GitHub Issues](https://github.com/corv89/shannot/issues)
- **Questions**: [GitHub Discussions](https://github.com/corv89/shannot/discussions)
- **Security issues**: Report privately via GitHub Security Advisories

---

**Last updated**: 2025-10-22
**Version**: Compatible with Shannot 0.2.0+
