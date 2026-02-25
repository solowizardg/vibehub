import asyncio
import json
import os
import sys
import time

# Add parent directory to path so we can import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings


def _truncate(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n... (truncated) ..."


def safe_print(text: str) -> None:
    """Print text safely in Windows consoles with GBK encoding."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("gbk", errors="replace").decode("gbk"))


async def run_cmd(sandbox, cmd: str, timeout: int = 120):
    """Run command and return (stdout, stderr, exit_code, elapsed_s)."""
    t0 = time.perf_counter()
    try:
        result = await sandbox.commands.run(cmd, timeout=timeout)
        elapsed = time.perf_counter() - t0
        return result.stdout or "", result.stderr or "", getattr(result, "exit_code", 0), elapsed
    except Exception as e:
        elapsed = time.perf_counter() - t0
        return "", str(e), getattr(e, "exit_code", 1), elapsed


async def run_bg(sandbox, cmd: str):
    """Run command in background and return (pid, error)."""
    try:
        handle = await sandbox.commands.run(cmd, background=True, timeout=0)
        return getattr(handle, "pid", None), ""
    except TypeError:
        try:
            handle = await sandbox.commands.run(cmd, background=True)
            return getattr(handle, "pid", None), ""
        except Exception as e:
            return None, str(e)
    except Exception as e:
        return None, str(e)


async def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: uv run python tests/test_sandbox_build_and_start.py <sandbox_id>")
        raise SystemExit(1)

    sandbox_id = sys.argv[1].strip()
    from e2b import AsyncSandbox

    if not settings.e2b_api_key:
        print("Error: No E2B_API_KEY found in .env")
        raise SystemExit(1)

    print(f"Connecting sandbox: {sandbox_id}")
    sandbox = await AsyncSandbox.connect(sandbox_id)
    print("Connected.")

    mem_before, _, _, _ = await run_cmd(
        sandbox,
        "bash -lc \"echo '=== meminfo ==='; egrep 'MemTotal|MemAvailable|SwapTotal|SwapFree' /proc/meminfo; "
        "echo; echo '=== free -m ==='; free -m\"",
        timeout=20,
    )
    print("\n[Memory before build]")
    print(mem_before)

    pkg_stdout, pkg_stderr, pkg_code, _ = await run_cmd(sandbox, "cat /home/user/project/package.json", timeout=20)
    if pkg_code != 0:
        print("Failed to read package.json:")
        print(pkg_stderr)
        raise SystemExit(2)

    try:
        pkg = json.loads(pkg_stdout)
    except json.JSONDecodeError:
        print("Invalid package.json")
        raise SystemExit(3)

    scripts = pkg.get("scripts", {}) if isinstance(pkg, dict) else {}
    deps = pkg.get("dependencies", {}) if isinstance(pkg, dict) else {}
    dev_deps = pkg.get("devDependencies", {}) if isinstance(pkg, dict) else {}
    is_next = "next" in deps or "next" in dev_deps
    is_vite = "vite" in deps or "vite" in dev_deps

    if "build" in scripts:
        build_cmd = "bash -lc \"cd /home/user/project && npm run build\""
    elif is_next:
        build_cmd = "bash -lc \"cd /home/user/project && npx next build\""
    elif is_vite:
        build_cmd = "bash -lc \"cd /home/user/project && npx vite build\""
    else:
        build_cmd = "bash -lc \"cd /home/user/project && npm run build\""

    if is_next:
        start_cmd = "bash -lc \"cd /home/user/project && npm run start -- -H 0.0.0.0 -p 3000 > /tmp/prodserver.log 2>&1\""
        port = 3000
    elif is_vite:
        start_cmd = "bash -lc \"cd /home/user/project && npm run preview -- --host 0.0.0.0 --port 4173 > /tmp/prodserver.log 2>&1\""
        port = 4173
    else:
        start_cmd = "bash -lc \"cd /home/user/project && npm run start > /tmp/prodserver.log 2>&1\""
        port = 3000

    print(f"\n[Build] {build_cmd}")
    build_out, build_err, build_code, build_elapsed = await run_cmd(sandbox, build_cmd, timeout=600)
    print(f"Build exit_code={build_code}, elapsed={build_elapsed:.1f}s")
    if build_out:
        print("\n[Build stdout]")
        safe_print(_truncate(build_out))
    if build_err:
        print("\n[Build stderr]")
        safe_print(_truncate(build_err))

    mem_after_build, _, _, _ = await run_cmd(
        sandbox,
        "bash -lc \"echo '=== meminfo ==='; egrep 'MemTotal|MemAvailable|SwapTotal|SwapFree' /proc/meminfo; "
        "echo; echo '=== free -m ==='; free -m\"",
        timeout=20,
    )
    print("\n[Memory after build]")
    print(mem_after_build)

    if build_code != 0:
        print("\nBuild failed; skip start.")
        raise SystemExit(4)

    await run_cmd(sandbox, "bash -lc \"pkill -f 'next|vite|node.*start|node.*preview' >/dev/null 2>&1 || true\"", timeout=20)
    await run_cmd(sandbox, "bash -lc \"rm -f /tmp/prodserver.log || true\"", timeout=10)

    print(f"\n[Start] {start_cmd}")
    pid, bg_err = await run_bg(sandbox, start_cmd)
    if bg_err:
        print(f"Start in background failed: {bg_err}")
        raise SystemExit(5)
    print(f"Background pid: {pid if pid is not None else '(unknown)'}")

    preview_url = ""
    for i in range(15):
        await asyncio.sleep(2)
        port_out, _, _, _ = await run_cmd(
            sandbox,
            f"bash -lc \"ss -tlnp | grep -E ':{port}\\s' || true\"",
            timeout=10,
        )
        if port_out.strip():
            preview_url = f"https://{sandbox.get_host(port)}"
            break
        print(f"Waiting port {port}... ({i + 1}/15)")

    print(f"\n[Port {port}] {'UP' if preview_url else 'DOWN'}")
    if preview_url:
        print(f"Preview URL: {preview_url}")
    else:
        print("No service listening.")

    log_out, log_err, _, _ = await run_cmd(
        sandbox,
        "bash -lc \"tail -n 120 /tmp/prodserver.log 2>/dev/null || echo 'No /tmp/prodserver.log found'\"",
        timeout=20,
    )
    print("\n[Start log]")
    safe_print(_truncate(log_out or log_err or "(empty)"))


if __name__ == "__main__":
    asyncio.run(main())
