# Deployment Guide

Practical deployment scenarios for Shannot in production environments.

## Quick Remote Deployment

### Direct SSH Install

Install Shannot on a remote Linux system via SSH:

```bash
# Using UV (recommended - fastest)
ssh user@remote "curl -LsSf https://astral.sh/uv/install.sh | sh && ~/.local/bin/uv tool install shannot"

# Or using pipx (if already available)
ssh user@remote "sudo apt install -y bubblewrap && pipx install shannot"

# Install only bubblewrap (if client is elsewhere)
ssh user@remote "sudo apt install -y bubblewrap"  # Debian/Ubuntu
ssh user@remote "sudo dnf install -y bubblewrap"  # Fedora/RHEL
```

## Configuration Management

### Ansible

Ansible playbook for deploying Shannot:

```yaml
# playbook.yml
---
- name: Deploy Shannot Sandbox
  hosts: all
  become: yes

  tasks:
    - name: Install bubblewrap
      package:
        name: bubblewrap
        state: present

    - name: Install pipx (Debian/Ubuntu)
      package:
        name: pipx
        state: present
      when: ansible_os_family == "Debian"

    - name: Install shannot with pipx
      become_user: "{{ deploy_user | default('shannot') }}"
      command: pipx install shannot
      args:
        creates: "~/.local/bin/shannot"

    - name: Create system config directory
      file:
        path: /etc/shannot
        state: directory
        mode: '0755'

    - name: Deploy minimal profile
      copy:
        src: files/minimal.json
        dest: /etc/shannot/profile.json
        mode: '0644'

    - name: Deploy diagnostics profile
      copy:
        src: files/diagnostics.json
        dest: /etc/shannot/diagnostics.json
        mode: '0644'

    - name: Verify installation
      become_user: "{{ deploy_user | default('shannot') }}"
      command: shannot verify
      register: verify_result
      changed_when: false
      failed_when: verify_result.rc != 0
```

Run with:
```bash
ansible-playbook -i inventory.ini playbook.yml
```

## SSH Integration

### Restricted Shell for Read-Only Access

Give SSH users read-only access by forcing all their commands through the sandbox:

```bash
# 1. Create dedicated user
sudo useradd -m -s /usr/local/bin/shannot-shell readonly-user

# 2. Create the wrapper shell script
sudo tee /usr/local/bin/shannot-shell > /dev/null << 'EOF'
#!/bin/bash
# Force all SSH commands through shannot sandbox

if [ -n "$SSH_ORIGINAL_COMMAND" ]; then
    # Run the user's command in the sandbox
    exec shannot $SSH_ORIGINAL_COMMAND
else
    # Interactive login not allowed
    echo "Error: This account only accepts SSH commands"
    echo "Usage: ssh readonly-user@host 'ls /var/log'"
    exit 1
fi
EOF

sudo chmod +x /usr/local/bin/shannot-shell

# 3. Test it
ssh readonly-user@host 'df -h'           # Works - runs in sandbox
ssh readonly-user@host 'cat /etc/passwd' # Works - read-only
ssh readonly-user@host 'rm /tmp/test'    # Fails - sandbox blocks writes
```

**How it works:**
- User SSHs in with a command: `ssh user@host 'df -h'`
- SSH sets `$SSH_ORIGINAL_COMMAND` to `df -h`
- The wrapper script runs `shannot df -h` instead
- Command executes in read-only sandbox
- User cannot get an interactive shell

### SSH Forced Command for Specific Keys

Restrict a specific SSH key to only run certain commands:

```bash
# /home/monitoring/.ssh/authorized_keys

# Allow only disk diagnostics with this key
command="shannot df -h" ssh-rsa AAAAB3NzaC1yc2E... user@laptop

# Allow a specific script with this key
command="shannot /usr/local/bin/system-health-check.sh" ssh-rsa AAAAB3NzaC1... monitoring@server
```

**How it works:**
- Regardless of what command the user tries to run, SSH forces the `command=` value
- The forced command runs through shannot automatically
- User cannot run anything else with that key

**Example:**
```bash
# User has key configured with: command="shannot df -h"

# User tries:
ssh -i monitoring.key user@host 'rm -rf /'

# SSH actually runs:
shannot df -h  # Ignores the 'rm -rf /' completely
```

## Remote Execution Setup

Control remote Linux systems from your macOS or Windows laptop.

### Quick Remote Setup

```bash
# 1. Ensure remote has bubblewrap installed
ssh user@remote "which bwrap || sudo apt install -y bubblewrap"

# 2. Add remote to shannot
shannot remote add myserver \
  --host remote.example.com \
  --user myuser \
  --key ~/.ssh/id_rsa

# 3. Test connection
shannot remote test myserver

# 4. Run commands
shannot -t myserver df -h
shannot -t myserver cat /etc/os-release
```

### Multi-Server Monitoring

Set up monitoring for multiple servers:

```bash
# Add all your servers
shannot remote add web1 web1.company.com --user monitoring
shannot remote add web2 web2.company.com --user monitoring
shannot remote add db1 db1.company.com --user monitoring --profile minimal

# Create monitoring script
cat > check-servers.sh << 'EOF'
#!/bin/bash
for server in web1 web2 db1; do
  echo "=== $server ==="
  echo "Disk:"
  shannot -t $server df -h / | tail -1
  echo "Memory:"
  shannot -t $server free -h | grep Mem:
  echo "Uptime:"
  shannot -t $server uptime
  echo
done
EOF

chmod +x check-servers.sh
./check-servers.sh
```

### Claude Desktop with Remote Access

Give Claude read-only access to your production servers:

```bash
# 1. Add production server
shannot remote add prod \
  --host prod.company.com \
  --user readonly \
  --key ~/.ssh/prod_readonly_key \
  --profile minimal

# 2. Test it works
shannot -t prod df -h

# 3. Install MCP with remote target
shannot mcp install --target prod

# 4. Restart Claude Desktop
# Now ask Claude: "Check disk space on the prod server"
```

## User-Specific Deployments

### Per-User Installation

Install for individual users without root:

```bash
# Install for current user
pip install --user shannot

# Create user config
mkdir -p ~/.config/shannot
cp profiles/minimal.json ~/.config/shannot/profile.json

# Verify
shannot verify
```

### User-Specific Profiles

Users can have custom profiles:

```bash
# Default: ~/.config/shannot/profile.json
shannot ls /

# Custom profile
shannot --profile ~/.config/shannot/diagnostics.json df -h

# Via environment variable
export SANDBOX_PROFILE=~/.config/shannot/custom.json
shannot cat /etc/os-release
```

## Troubleshooting Deployments

### Verify Bubblewrap Installation

Check that bubblewrap is properly installed:

```bash
# Check if bwrap is installed
which bwrap

# Check version
bwrap --version

# Test basic functionality (should fail with "No permissions" - this is expected)
bwrap --ro-bind / / --dev /dev --proc /proc ls / 2>&1 | grep -q "unshare" && echo "Needs user namespace support - see troubleshooting.md"
```

**Note:** Bubblewrap uses unprivileged user namespaces, not setuid. If you see permission errors, see [troubleshooting.md](troubleshooting.md) for platform-specific fixes.

### Test Profile

Verify profile is valid:

```bash
# Validate syntax
shannot --profile /etc/shannot/profile.json export > /dev/null

# Test basic command
shannot --profile /etc/shannot/profile.json ls /

# Verbose mode for debugging
shannot --verbose --profile /etc/shannot/profile.json verify
```

### Network Isolation

Test that network is properly isolated:

```bash
# Should fail (network isolated by default)
shannot ping -c 1 8.8.8.8

# Should succeed (reading local file)
shannot cat /etc/resolv.conf
```

### Profile Path Issues

If profile isn't found:

```bash
# Check search order (verbose mode shows which profiles are tried)
shannot --verbose ls / 2>&1 | grep profile

# Specify explicitly with environment variable
export SANDBOX_PROFILE=/etc/shannot/profile.json
shannot ls /

# Or use command line flag
shannot --profile /etc/shannot/profile.json ls /
```

## Security Considerations

### File Permissions

Ensure profiles are protected:

```bash
# System profiles should be root-owned
sudo chown root:root /etc/shannot/*.json
sudo chmod 644 /etc/shannot/*.json

# User profiles
chmod 600 ~/.config/shannot/profile.json
```

### Profile Validation

Always validate profiles before deployment:

```bash
# Test in non-production first
shannot --profile new-profile.json verify

# Check for overly permissive settings
jq '.network_isolation' new-profile.json  # Should be true
jq '.allowed_commands' new-profile.json    # Should be minimal
```

### Audit Logging

Enable audit logging for sandboxed commands:

```bash
# Log all shannot invocations
alias shannot='logger -t shannot "User $USER command: $*"; /usr/bin/shannot'
```

## Best Practices

1. **Start Minimal** - Use `minimal.json` as default, expand as needed
2. **Test Profiles** - Always run `shannot verify` after deployment
3. **Separate Profiles** - Different profiles for different use cases
4. **Monitor Logs** - Set up centralized logging early
5. **Update Regularly** - Keep shannot and bubblewrap updated
6. **Document Changes** - Track profile modifications
7. **Backup Profiles** - Version control your profiles

## See Also

- [installation.md](installation.md) - Installation details
- [usage.md](usage.md) - Basic usage
- [api.md](api.md) - Python API for automation
- [profiles.md](profiles.md) - Profile configuration
