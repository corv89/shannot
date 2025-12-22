# Shannot - Sandboxed System Diagnostics

Run diagnostic scripts in a sandbox with human approval.

## Usage

```bash
# Run a script locally
shannot run /path/to/pypy-sandbox -S /tmp/script.py

# Run against a remote host (files fetched via SSH)
shannot run /path/to/pypy-sandbox -S /tmp/script.py --target user@host

# Dry-run mode (queue all operations for review)
shannot run /path/to/pypy-sandbox -S /tmp/script.py --dry-run
```

After running with `--dry-run`, instruct the user to open `shannot approve` to review and execute queued operations.

## Writing Scripts

Scripts run in a virtualized environment with Python 3.6 syntax.

### Running Commands

```python
import subprocess

# Commands are intercepted and queued for approval
result = subprocess.run(["ls", "-la", "/etc"], capture_output=True, text=True)
print(result.stdout)
```

### Reading Files

```python
# File reads are allowed within the virtual filesystem
with open("/etc/hostname") as f:
    print(f.read())
```

### Writing Files

```python
# Writes are queued for approval, not executed immediately
with open("/tmp/output.txt", "w") as f:
    f.write("diagnostic results")
```

## Security Model

- **Reads**: Allowed within virtual filesystem boundaries
- **Commands**: Queued for human approval (or auto-approved via profile)
- **Writes**: Queued for human approval
- **Network**: Disabled (socket calls return errors)

## Tips

- Keep scripts focused on diagnostics and information gathering
- Use `--dry-run` to preview what operations a script will request
- Tell the user to run `shannot approve` to review queued operations
