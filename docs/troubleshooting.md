# Troubleshooting Guide

This guide covers common issues when deploying shannot and their solutions.

## User Namespace Permission Issues

### Symptoms

```
ERROR: Sandbox error: Sandbox command failed with exit code 1
Stderr: bwrap: setting up uid map: Permission denied
```

or

```
ERROR: Sandbox error: Sandbox command failed with exit code 1
Stderr: bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted
```

### Root Cause

Unprivileged user namespace creation is blocked by the kernel or security policies. This is required by bubblewrap to create isolated sandbox environments.

### Solutions by Distribution

#### Ubuntu 24.04+ (AppArmor Restriction)

Ubuntu 24.04 and newer restrict unprivileged user namespaces via AppArmor for security reasons.

**Temporary fix:**
```bash
sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0
```

**Permanent fix:**
```bash
echo 'kernel.apparmor_restrict_unprivileged_userns=0' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

**Verify it works:**
```bash
shannot run ls /
```

#### Other Distributions

**Check current status:**
```bash
# Should return 1 (enabled)
cat /proc/sys/kernel/unprivileged_userns_clone

# Should return a positive number
cat /proc/sys/user/max_user_namespaces
```

**Enable if needed:**
```bash
# Temporary
sudo sysctl -w kernel.unprivileged_userns_clone=1

# Permanent
echo 'kernel.unprivileged_userns_clone=1' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

### Why Not Use Setuid Bubblewrap?

You might wonder why we don't just make bubblewrap setuid root, which would bypass these restrictions.

**Security Risk:**
- Setuid root binaries run with full system privileges
- Any vulnerability in bubblewrap = instant root access
- Goes against the principle of least privilege
- Modern security best practices avoid setuid where possible

**Philosophy:**
- Shannot is designed for **read-only diagnostics** - we want isolation *from* privilege
- Defense in depth: even if the sandbox escapes, the attacker only has user permissions
- Unprivileged user namespaces are the modern, secure approach

**Recommendation:**
Configure your system properly (one-time setup) rather than introducing setuid risk.

## Container/VM Environment Issues

### Symptoms

```
ERROR: Sandbox error: Sandbox command failed with exit code 1
Stderr: bwrap: pivot_root: Operation not permitted
```

### Root Cause

Running in a restricted container environment (Docker, Kubernetes, GitHub Codespaces) that doesn't allow the required Linux capabilities.

### Solutions

1. **Best:** Use a real Linux VM (AWS EC2, GCP, Azure, local VM)
2. **Good:** Use WSL2 on Windows (supports user namespaces)
3. **Alternative:** Run on native Linux (Ubuntu, Fedora, etc.)
4. **Not Recommended:** Enable privileged containers (security risk)

## Getting Help

If you're still stuck after trying these solutions:

1. Check kernel version: `uname -r`
2. Check distribution: `cat /etc/os-release`
3. Test unshare directly: `unshare --user --map-root-user whoami`
4. Check AppArmor: `sudo aa-status | grep unprivileged`
5. Open an issue: https://github.com/corv89/shannot/issues

Include the output of all the above commands in your issue report.

## Security Considerations

When modifying system security settings:

- **Understand the implications** - disabling security features reduces system security
- **Scope appropriately** - apply changes only where needed (dev VMs, not production servers)
- **Document changes** - keep track of what you've modified and why
- **Review periodically** - security policies evolve, revisit your configuration

The solutions in this guide are appropriate for:
- Development environments
- Testing VMs
- Controlled deployment scenarios

For production systems, consult your security team before modifying kernel security settings.
