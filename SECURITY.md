# Security Policy

## Overview

Shannot is a security tool designed to provide read-only sandboxed execution environments using Linux namespaces and Bubblewrap. While it provides strong isolation for many use cases, **it is not a complete security boundary** and should be used as part of a defense-in-depth strategy.

## Supported Versions

We provide security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 0.2.x   | :white_check_mark: |
| 0.1.x   | :white_check_mark: |
| < 0.1.0 | :x:                |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

### Private Disclosure Process

If you discover a security vulnerability in Shannot, please report it privately:

1. **Email**: Send details to **corv89@users.noreply.github.com**
   - Include "SECURITY" in the subject line
   - Provide a detailed description of the vulnerability
   - Include steps to reproduce if possible
   - Mention any potential impact or exploit scenarios

2. **GitHub Security Advisory**: Alternatively, use GitHub's private vulnerability reporting:
   - Go to https://github.com/corv89/shannot/security/advisories
   - Click "Report a vulnerability"
   - Fill in the advisory form

### What to Expect

- **Acknowledgment**: We will acknowledge receipt within 48 hours
- **Assessment**: We will assess the vulnerability and determine its severity
- **Fix Timeline**:
  - Critical vulnerabilities: Fix within 7 days
  - High severity: Fix within 30 days
  - Medium/Low severity: Fix in next release
- **Disclosure**: We will coordinate public disclosure with you after a fix is available
- **Credit**: You will be credited in the security advisory (unless you prefer to remain anonymous)

### Bug Bounty

We do not currently offer a bug bounty program, but we deeply appreciate security research and responsible disclosure.

## Security Considerations

### What Shannot Provides

Shannot provides strong isolation through:

- **Read-only filesystem access**: Host filesystem mounted read-only (except tmpfs)
- **Namespace isolation**: Separate PID, mount, network, IPC, and UTS namespaces
- **Command filtering**: Only allowed commands can be executed
- **Network isolation**: Network access disabled by default
- **Minimal attack surface**: No daemon, runs as regular user

### Known Limitations

⚠️ **Important**: Shannot is NOT a complete security boundary. Known limitations include:

#### 1. Kernel Exploits

- **Risk**: Sandbox escapes possible via kernel vulnerabilities
- **Mitigation**:
  - Keep kernel updated with latest security patches
  - Use hardened kernel configurations
  - Consider SELinux or AppArmor for additional MAC (Mandatory Access Control)
  - Add seccomp filters to restrict system calls (see [docs/seccomp.md](docs/seccomp.md))

#### 2. Information Disclosure

- **Risk**: Read-only access still exposes system information
- **Impact**: Users can read mounted paths and see some system state
- **Mitigation**:
  - Carefully control which paths are mounted in profiles
  - Review profiles to ensure no sensitive data is exposed
  - Use restrictive bind mounts (only mount what's needed)
  - Consider using separate machines for truly sensitive data

#### 3. Resource Exhaustion

- **Risk**: No built-in CPU/memory/disk limits
- **Impact**: Sandboxed processes can consume system resources
- **Mitigation**:
  - Use systemd resource controls (`MemoryMax`, `CPUQuota`)
  - Use cgroups v2 for fine-grained resource limits
  - Set ulimits in shell or systemd units
  - Monitor resource usage

Example systemd unit with resource limits:
```ini
[Service]
MemoryMax=512M
CPUQuota=50%
TasksMax=100
```

#### 4. Side-Channel Attacks

- **Risk**: Timing attacks, speculative execution vulnerabilities
- **Impact**: Potential information leakage through timing or cache behavior
- **Mitigation**:
  - Keep CPU microcode updated
  - Use kernel mitigations (KPTI, IBPB, etc.)
  - Don't run untrusted code alongside sensitive workloads

#### 5. Privilege Escalation

- **Risk**: Running as root increases attack surface
- **Impact**: If sandbox is compromised, attacker has root access
- **Mitigation**:
  - **Never run Shannot as root unless absolutely necessary**
  - Use unprivileged user namespaces when possible
  - Apply principle of least privilege
  - Use dedicated service accounts with minimal permissions

#### 6. Bubblewrap Dependencies

- **Risk**: Security relies on Bubblewrap being correctly implemented
- **Impact**: Vulnerabilities in Bubblewrap affect Shannot
- **Mitigation**:
  - Keep Bubblewrap updated (install from distro packages for security updates)
  - Monitor Bubblewrap security advisories
  - Follow Bubblewrap best practices

## Security Best Practices

### For Users

#### Profile Configuration

1. **Principle of Least Privilege**
   ```json
   {
     "name": "minimal",
     "allowed_commands": ["ls", "cat"],  // Only what's needed
     "binds": [
       {"source": "/usr", "target": "/usr", "read_only": true},
       {"source": "/etc", "target": "/etc", "read_only": true}
     ],
     "network_isolation": true  // Keep network disabled unless needed
   }
   ```

2. **Avoid Mounting Sensitive Paths**
   - Don't mount `/root`, `/home`, or SSH keys unless absolutely required
   - Be cautious with `/etc` (contains passwords, configs)
   - Review all bind mounts for sensitive data

3. **Enable Network Isolation**
   - Keep `network_isolation: true` (default) unless network is required
   - If network needed, use firewall rules to restrict connections

4. **Add Seccomp Filters**
   - Use seccomp to restrict system calls (see [docs/seccomp.md](docs/seccomp.md))
   - Start with restrictive filters and expand as needed

#### Production Deployment

1. **Defense in Depth**
   ```bash
   # Layer security controls
   - Shannot sandbox (namespace isolation)
   - SELinux/AppArmor (MAC)
   - Seccomp filters (syscall filtering)
   - systemd resource limits (resource control)
   - Firewall rules (network control)
   ```

2. **Run as Unprivileged User**
   ```bash
   # Create dedicated user
   sudo useradd -r -s /bin/false shannot-runner

   # Run sandbox as that user
   sudo -u shannot-runner shannot ls /
   ```

3. **Monitor and Audit**
   - Log all sandbox invocations
   - Monitor for unexpected behavior
   - Review logs regularly for anomalies
   - Use auditd to track system calls

4. **Update Regularly**
   - Keep Shannot updated: `pipx upgrade shannot`
   - Keep Bubblewrap updated via distro packages
   - Keep kernel updated with security patches

#### SSH Remote Execution

1. **Use SSH Key Authentication**
   - Never use password authentication for automation
   - Use dedicated SSH keys with restricted permissions
   - Consider using `authorized_keys` restrictions

2. **Restrict SSH Commands**
   ```
   # In ~/.ssh/authorized_keys
   command="shannot ls /" ssh-rsa AAAA...
   ```

3. **Use Non-Root SSH User**
   - Connect as unprivileged user
   - Use sudo only if absolutely required

### For Developers

#### Contributing Security Fixes

1. **Review Security Implications**
   - Consider how changes affect sandbox isolation
   - Review bind mounts and namespace configuration
   - Test with malicious inputs

2. **Add Tests**
   - Add security-focused tests for new features
   - Test edge cases and error conditions
   - Verify isolation properties

3. **Follow Secure Coding Practices**
   - Validate all inputs
   - Use type hints and static analysis
   - Avoid eval() and exec()
   - Handle errors gracefully

## Security Resources

### Documentation

- [Seccomp Filters Guide](docs/seccomp.md) - Adding syscall restrictions
- [Deployment Guide](docs/deployment.md) - Production deployment patterns
- [Profile Configuration](docs/profiles.md) - Secure profile setup
- [Troubleshooting](docs/troubleshooting.md) - Common security issues

### External Resources

- [Bubblewrap](https://github.com/containers/bubblewrap) - Underlying sandboxing tool
- [Linux Namespaces](https://man7.org/linux/man-pages/man7/namespaces.7.html) - Namespace documentation
- [Seccomp](https://www.kernel.org/doc/html/latest/userspace-api/seccomp_filter.html) - Seccomp filter documentation
- [SELinux](https://selinuxproject.org/) - Mandatory Access Control
- [AppArmor](https://apparmor.net/) - Application security framework

### Security Advisories

We will publish security advisories at:
- GitHub Security Advisories: https://github.com/corv89/shannot/security/advisories
- Release notes with `[SECURITY]` tag

Subscribe to repository releases to receive security notifications.

## Responsible Use

Shannot is designed for legitimate use cases:
- **✅ System diagnostics and monitoring**
- **✅ Read-only access for automation**
- **✅ LLM agent sandboxing**
- **✅ Security research and testing**

## Acknowledgments

We thank the security research community for helping keep Shannot secure. Security researchers who responsibly disclose vulnerabilities will be credited in our security advisories.

## Contact

For security concerns: corv89@users.noreply.github.com (Subject: SECURITY)

For general issues: https://github.com/corv89/shannot/issues

---

**Remember**: Shannot is a tool for defense-in-depth, not a complete security solution. Always use multiple layers of security controls in production environments.
