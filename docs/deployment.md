# Deployment Guide

Practical deployment scenarios for Shannot in production environments.

## Quick Remote Deployment

### Direct SSH Install

```bash
# Install on remote system via SSH using pipx
ssh user@remote "sudo apt install -y bubblewrap pipx && pipx install shannot && pipx ensurepath"

# Or using uv (fastest)
ssh user@remote "curl -LsSf https://astral.sh/uv/install.sh | sh && ~/.cargo/bin/uv tool install shannot"
```

## Configuration Management

### Ansible

Basic Ansible playbook for installing shannot:

```yaml
# playbook.yml
---
- name: Deploy Shannot Sandbox
  hosts: all
  become: yes

  tasks:
    - name: Install dependencies
      package:
        name:
          - python3
          - python3-pip
          - bubblewrap
        state: present

    - name: Install shannot
      pip:
        name: shannot
        state: present
        executable: pip3

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

### Restricted Shell for Specific Users

Create a dedicated user that can only run sandboxed commands:

```bash
# Create monitoring user
sudo useradd -m -s /bin/bash monitoring

# Create wrapper script
sudo cat > /usr/local/bin/shannot-shell << 'EOF'
#!/bin/bash
# Wrapper that runs all commands in sandbox

if [ -n "$SSH_ORIGINAL_COMMAND" ]; then
    exec /usr/bin/shannot run $SSH_ORIGINAL_COMMAND
else
    echo "This account can only run specific commands"
    echo "Usage: ssh monitoring@host 'command'"
    exit 1
fi
EOF

sudo chmod +x /usr/local/bin/shannot-shell

# Set as user's shell
sudo usermod -s /usr/local/bin/shannot-shell monitoring
```

### SSH Forced Command

Restrict SSH keys to sandboxed commands only:

```bash
# /home/monitoring/.ssh/authorized_keys
command="/usr/bin/shannot run /usr/local/bin/diagnostics.sh" ssh-rsa AAAA...
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
shannot run ls /

# Custom profile
shannot --profile ~/.config/shannot/diagnostics.json run df -h

# Via environment variable
export SANDBOX_PROFILE=~/.config/shannot/custom.json
shannot run cat /etc/os-release
```

## Troubleshooting Deployments

### Verify Permissions

Check bubblewrap permissions:

```bash
ls -la $(which bwrap)
# Should be: -rwsr-xr-x (setuid root)

# If not, fix:
sudo chmod u+s $(which bwrap)
```

### Test Profile

Verify profile is valid:

```bash
# Validate syntax
shannot --profile /etc/shannot/profile.json export > /dev/null

# Test basic command
shannot --profile /etc/shannot/profile.json run ls /

# Verbose mode for debugging
shannot --verbose --profile /etc/shannot/profile.json verify
```

### Network Isolation

Test that network is properly isolated:

```bash
# Should fail (network isolated)
shannot run ping -c 1 8.8.8.8

# Should succeed (reading local file)
shannot run cat /etc/resolv.conf
```

### Profile Path Issues

If profile isn't found:

```bash
# Check search order
shannot --verbose run ls / 2>&1 | grep profile

# Specify explicitly
export SANDBOX_PROFILE=/etc/shannot/profile.json
shannot run ls /

# Or use command line
shannot --profile /etc/shannot/profile.json run ls /
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
