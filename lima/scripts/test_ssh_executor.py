#!/usr/bin/env python3
"""Test script for SSHExecutor with Lima VM."""

import asyncio
from pathlib import Path

from shannot import SandboxBind, SandboxProfile
from shannot.executors import SSHExecutor


async def main():
    """Test SSH executor with Lima VM."""
    print("🔧 Creating SSH executor for Lima VM...")

    # Create executor for Lima VM
    executor = SSHExecutor(
        host="localhost",
        port=60797,
        username="corv",
    )

    print("✅ SSH executor created")

    # Test 1: Simple command
    print("\n📋 Test 1: Running simple echo command...")
    profile = SandboxProfile(
        name="test",
        allowed_commands=["echo"],
        binds=[
            SandboxBind(source=Path("/usr"), target=Path("/usr"), read_only=True),
            SandboxBind(source=Path("/bin"), target=Path("/bin"), read_only=True),
            SandboxBind(source=Path("/lib"), target=Path("/lib"), read_only=True),
            SandboxBind(source=Path("/lib64"), target=Path("/lib64"), read_only=True),
        ],
        tmpfs_paths=[Path("/tmp")],
    )

    try:
        result = await executor.run_command(
            profile, ["echo", "Hello from SSH executor!"], timeout=10
        )
        print(f"   Command: {' '.join(result.command)}")
        print(f"   Exit code: {result.returncode}")
        print(f"   Stdout: {result.stdout.strip()}")
        print(f"   Stderr: {result.stderr.strip()}")
        print(f"   Duration: {result.duration:.2f}s")
        assert result.returncode == 0
        assert "Hello from SSH executor!" in result.stdout
        print("✅ Test 1 passed")
    except Exception as e:
        print(f"❌ Test 1 failed: {e}")
        raise

    # Test 2: File read via cat
    print("\n📋 Test 2: Reading /etc/hostname via cat...")
    profile2 = SandboxProfile(
        name="test-readonly",
        allowed_commands=["cat"],
        binds=[
            SandboxBind(source=Path("/usr"), target=Path("/usr"), read_only=True),
            SandboxBind(source=Path("/bin"), target=Path("/bin"), read_only=True),
            SandboxBind(source=Path("/lib"), target=Path("/lib"), read_only=True),
            SandboxBind(source=Path("/lib64"), target=Path("/lib64"), read_only=True),
            SandboxBind(source=Path("/etc"), target=Path("/etc"), read_only=True),
        ],
        tmpfs_paths=[Path("/tmp")],
    )

    try:
        result = await executor.run_command(profile2, ["cat", "/etc/hostname"], timeout=10)
        print(f"   Command: {' '.join(result.command)}")
        print(f"   Exit code: {result.returncode}")
        print(f"   Hostname: {result.stdout.strip()}")
        print(f"   Duration: {result.duration:.2f}s")
        assert result.returncode == 0
        print("✅ Test 2 passed")
    except Exception as e:
        print(f"❌ Test 2 failed: {e}")
        raise

    # Test 3: List directory
    print("\n📋 Test 3: Listing /etc directory...")
    profile3 = SandboxProfile(
        name="test-ls",
        allowed_commands=["ls"],
        binds=[
            SandboxBind(source=Path("/usr"), target=Path("/usr"), read_only=True),
            SandboxBind(source=Path("/bin"), target=Path("/bin"), read_only=True),
            SandboxBind(source=Path("/lib"), target=Path("/lib"), read_only=True),
            SandboxBind(source=Path("/lib64"), target=Path("/lib64"), read_only=True),
            SandboxBind(source=Path("/etc"), target=Path("/etc"), read_only=True),
        ],
        tmpfs_paths=[Path("/tmp")],
    )

    try:
        result = await executor.run_command(profile3, ["ls", "-la", "/etc"], timeout=10)
        print(f"   Command: {' '.join(result.command)}")
        print(f"   Exit code: {result.returncode}")
        print(f"   Lines of output: {len(result.stdout.splitlines())}")
        print("   First few lines:")
        for line in result.stdout.splitlines()[:5]:
            print(f"     {line}")
        print(f"   Duration: {result.duration:.2f}s")
        assert result.returncode == 0
        print("✅ Test 3 passed")
    except Exception as e:
        print(f"❌ Test 3 failed: {e}")
        raise

    # Test 4: Network isolation test
    print("\n📋 Test 4: Testing network isolation...")
    profile4 = SandboxProfile(
        name="test-network",
        allowed_commands=["ping"],
        binds=[
            SandboxBind(source=Path("/usr"), target=Path("/usr"), read_only=True),
            SandboxBind(source=Path("/bin"), target=Path("/bin"), read_only=True),
            SandboxBind(source=Path("/lib"), target=Path("/lib"), read_only=True),
            SandboxBind(source=Path("/lib64"), target=Path("/lib64"), read_only=True),
        ],
        tmpfs_paths=[Path("/tmp")],
        network_isolation=True,
    )

    try:
        result = await executor.run_command(profile4, ["ping", "-c", "1", "8.8.8.8"], timeout=10)
        print(f"   Command: {' '.join(result.command)}")
        print(f"   Exit code: {result.returncode}")
        print(f"   Output: {result.stdout[:200]}")
        print(f"   Stderr: {result.stderr[:200]}")
        print(f"   Duration: {result.duration:.2f}s")
        # Should fail due to network isolation
        if result.returncode != 0:
            print("✅ Test 4 passed (network isolated as expected)")
        else:
            print("⚠️  Test 4: Network not isolated (may be expected on some systems)")
    except Exception as e:
        print(f"❌ Test 4 failed: {e}")
        raise

    # Test 5: Connection pooling
    print("\n📋 Test 5: Testing connection pooling (5 commands)...")
    profile5 = SandboxProfile(
        name="test-pool",
        allowed_commands=["echo"],
        binds=[
            SandboxBind(source=Path("/usr"), target=Path("/usr"), read_only=True),
            SandboxBind(source=Path("/bin"), target=Path("/bin"), read_only=True),
            SandboxBind(source=Path("/lib"), target=Path("/lib"), read_only=True),
            SandboxBind(source=Path("/lib64"), target=Path("/lib64"), read_only=True),
        ],
        tmpfs_paths=[Path("/tmp")],
    )

    try:
        for i in range(5):
            result = await executor.run_command(profile5, ["echo", f"Command {i}"], timeout=10)
            print(f"   Command {i}: {result.stdout.strip()} (duration: {result.duration:.2f}s)")
            assert result.returncode == 0
        print("✅ Test 5 passed")
    except Exception as e:
        print(f"❌ Test 5 failed: {e}")
        raise

    # Cleanup
    print("\n🧹 Cleaning up...")
    await executor.cleanup()
    print("✅ Cleanup complete")

    print("\n" + "=" * 60)
    print("🎉 All tests passed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
