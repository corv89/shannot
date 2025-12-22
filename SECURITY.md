# Security Policy

## Overview

Shannot is a security tool designed to provide sandboxed execution environments using PyPy's sandbox mode with system call interception. While it provides strong isolation for many use cases, **it is not a complete security boundary** and should be used as part of a defense-in-depth strategy.

## Supported Versions

We provide security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 0.4.x   | :white_check_mark: |
| < 0.4.0 | :x:                |

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

- **System call interception**: All system calls from sandboxed code are intercepted and mediated by the host process
- **Virtual filesystem**: File operations are virtualized, providing controlled access to the real filesystem
- **Subprocess approval workflow**: Commands executed by sandboxed code require explicit approval
- **Network isolation**: Socket operations are disabled in the sandbox
- **Minimal attack surface**: No daemon, runs as regular user, zero external dependencies

### Known Limitations

⚠️ **Important**: Shannot is NOT a complete security boundary. Known limitations include:

#### 1. PyPy Sandbox Interpreter Vulnerabilities

- **Risk**: Vulnerabilities in the PyPy sandbox implementation could allow escape
- **Impact**: Attacker could gain access to host system
- **Mitigation**:
  - Keep PyPy sandbox updated with latest security patches
  - Monitor PyPy security announcements
  - Use defense-in-depth: don't rely solely on sandbox isolation
  - Consider running Shannot itself in a VM or container for high-risk workloads

#### 2. Information Disclosure

- **Risk**: Sandboxed code can read files through the virtual filesystem
- **Impact**: Sensitive information in mapped paths may be exposed
- **Mitigation**:
  - Carefully control which directories are accessible to the sandbox
  - Use minimal directory mappings (only what's needed)
  - Review what files are visible before running untrusted code
  - Consider using separate machines for truly sensitive data
  - Audit approval profiles to ensure safe commands only

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

#### 4. Subprocess Execution

- **Risk**: Approval workflow depends on human review
- **Impact**: Approved commands execute with host privileges
- **Mitigation**:
  - Use restrictive approval profiles (only safe commands in auto-approve list)
  - Review command queues carefully before approving
  - Use dry-run mode to preview operations
  - Implement audit logging for all approvals

#### 5. Privilege Escalation

- **Risk**: Running as root increases attack surface
- **Impact**: If sandbox is compromised, attacker has root access
- **Mitigation**:
  - **Never run Shannot as root unless absolutely necessary**
  - Use unprivileged user accounts
  - Apply principle of least privilege
  - Use dedicated service accounts with minimal permissions

#### 6. PyPy Sandbox Dependencies

- **Risk**: Security relies on PyPy sandbox implementation being correct
- **Impact**: Vulnerabilities in PyPy affect Shannot
- **Mitigation**:
  - Keep PyPy sandbox updated (auto-downloaded version is checked)
  - Monitor PyPy security advisories
  - Follow PyPy sandbox best practices

## Security Best Practices

### For Users

#### Profile Configuration

1. **Principle of Least Privilege**
   ```json
   {
     "auto_approve": [
       "ls", "cat", "grep"
     ],
     "always_deny": [
       "rm -rf /",
       "dd if=/dev/zero",
       "chmod 777"
     ]
   }
   ```

2. **Use Restrictive Auto-Approve Lists**
   - Only include truly safe, read-only commands
   - Avoid commands that can modify system state
   - Review the default profile and customize for your needs

3. **Always Deny Dangerous Commands**
   - Block destructive operations
   - Prevent privilege escalation attempts
   - Add patterns for risky command combinations

#### Production Deployment

1. **Defense in Depth**
   ```bash
   # Layer security controls
   - Shannot sandbox (syscall interception)
   - systemd resource limits (resource control)
   - Firewall rules (network control)
   - SELinux/AppArmor (optional, for additional MAC)
   ```

2. **Run as Unprivileged User**
   ```bash
   # Create dedicated user
   sudo useradd -r -s /bin/false shannot-runner

   # Run sandbox as that user
   sudo -u shannot-runner shannot run script.py
   ```

3. **Monitor and Audit**
   - Log all sandbox invocations
   - Monitor for unexpected behavior
   - Review approval logs regularly
   - Track session execution patterns

4. **Update Regularly**
   - Keep Shannot updated: `pip install --upgrade shannot`
   - Keep Python updated with security patches
   - Monitor for PyPy sandbox updates

#### SSH Remote Execution

1. **Use SSH Key Authentication**
   - Never use password authentication for automation
   - Use dedicated SSH keys with restricted permissions
   - Consider using `authorized_keys` restrictions

2. **Restrict SSH Commands**
   ```
   # In ~/.ssh/authorized_keys
   command="shannot execute --session-id ${SSH_ORIGINAL_COMMAND}" ssh-rsa AAAA...
   ```

3. **Use Non-Root SSH User**
   - Connect as unprivileged user
   - Use sudo only if absolutely required

### For Developers

#### Contributing Security Fixes

1. **Review Security Implications**
   - Consider how changes affect sandbox isolation
   - Review virtual filesystem and syscall interception code
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

- [README.md](README.md) - Overview and usage
- [CONTRIBUTING.md](CONTRIBUTING.md) - Development guidelines
- [BUILDING.md](BUILDING.md) - Binary building guide

### External Resources

- [PyPy Sandbox](https://doc.pypy.org/en/latest/sandbox.html) - PyPy sandbox documentation
- [Python Security](https://python.org/dev/security/) - Python security resources
- [OWASP](https://owasp.org/) - Web application security

### Security Advisories

We will publish security advisories at:
- GitHub Security Advisories: https://github.com/corv89/shannot/security/advisories
- Release notes with `[SECURITY]` tag

Subscribe to repository releases to receive security notifications.

## Responsible Use

Shannot is designed for legitimate use cases:
- **✅ System diagnostics and monitoring**
- **✅ Safe code exploration for LLM agents**
- **✅ Controlled script execution**
- **✅ Security research and testing**

## Acknowledgments

We thank the security research community for helping keep Shannot secure. Security researchers who responsibly disclose vulnerabilities will be credited in our security advisories.

## Contact

For security concerns: corv89@users.noreply.github.com (Subject: SECURITY)

For general issues: https://github.com/corv89/shannot/issues

---

**Remember**: Shannot is a tool for defense-in-depth, not a complete security solution. Always use multiple layers of security controls in production environments.
