import asyncio
import json
import os
import sys

# Add parent directory to path so we can import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings


def safe_print(text: str) -> None:
    """Print text safely in Windows consoles with GBK encoding."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("gbk", errors="replace").decode("gbk"))


async def run_cmd(sandbox, command: str):
    """Run command and always return (stdout, stderr, exit_code)."""
    try:
        res = await sandbox.commands.run(command)
        return res.stdout or "", res.stderr or "", getattr(res, "exit_code", 0)
    except Exception as e:
        return "", str(e), getattr(e, "exit_code", 1)


async def run_cmd_bg(sandbox, command: str):
    """Run command in background and return pid or error text."""
    try:
        handle = await sandbox.commands.run(command, background=True, timeout=0)
        return str(getattr(handle, "pid", "") or ""), ""
    except TypeError:
        try:
            handle = await sandbox.commands.run(command, background=True)
            return str(getattr(handle, "pid", "") or ""), ""
        except Exception as e:
            return "", str(e)
    except Exception as e:
        return "", str(e)


async def check(sandbox_id: str, start_server: bool = False, repair: bool = False):
    if not settings.e2b_api_key:
        print("Error: No E2B_API_KEY found in .env")
        return

    from e2b import AsyncSandbox
    
    print(f"尝试连接到 Sandbox: {sandbox_id} ...")
    try:
        sandbox = await AsyncSandbox.connect(sandbox_id)
        print("连接成功！\n")
    except Exception as e:
        print(f"连接失败，可能是由于沙盒已过期销毁或 ID 错误: {e}")
        return
    
    print("--- 1. 检查端口监听 ---")
    res1 = await sandbox.commands.run("ss -tlnp | grep -E '3000|5173' || echo 'No ports listening on 3000 or 5173'")
    print(res1.stdout)
    
    print("\n--- 2. 检查 Next.js / Vite 进程 ---")
    res2 = await sandbox.commands.run("ps aux | grep -E 'next|vite' || echo 'No dev server process found'")
    print(res2.stdout)
    
    print("\n--- 3. 检查代码目录结构 ---")
    res3 = await sandbox.commands.run("ls -la /home/user/project")
    print(res3.stdout)
    
    print("\n--- 4. 检查构建产物 ---")
    res4_stdout, _, _ = await run_cmd(
        sandbox, "ls -la /home/user/project/.next/server || echo 'No .next/server built yet'",
    )
    print(res4_stdout)

    print("\n--- 5. 检查项目配置（不做修复） ---")
    cfg_stdout, _, _ = await run_cmd(
        sandbox,
        "bash -lc \"ls -la /home/user/project/next.config.* 2>/dev/null || echo 'No next.config.* found'\"",
    )
    print(cfg_stdout)

    pkg_res_stdout, pkg_res_stderr, _ = await run_cmd(sandbox, "cat /home/user/project/package.json")
    package_json = {}
    try:
        package_json = json.loads(pkg_res_stdout or "{}")
    except json.JSONDecodeError:
        package_json = {}
        if pkg_res_stderr:
            safe_print(pkg_res_stderr)

    scripts = package_json.get("scripts", {}) if isinstance(package_json, dict) else {}
    deps = package_json.get("dependencies", {}) if isinstance(package_json, dict) else {}
    dev_deps = package_json.get("devDependencies", {}) if isinstance(package_json, dict) else {}
    dev_script = scripts.get("dev", "") if isinstance(scripts, dict) else ""

    start_cmd = "npm run dev"
    expected_port = 3000
    if "next" in deps or "next" in dev_deps or "next" in dev_script:
        start_cmd = "npx next dev -H 0.0.0.0 -p 3000"
        expected_port = 3000
    elif "vite" in deps or "vite" in dev_deps or "vite" in dev_script:
        start_cmd = "npx vite --host 0.0.0.0 --port 5173"
        expected_port = 5173

    print(f"推断启动命令: {start_cmd}")
    port_stdout, _, _ = await run_cmd(
        sandbox,
        f"bash -lc \"ss -tlnp | grep -E ':{expected_port}\\s' || true\""
    )
    print(f"\n端口 {expected_port} 监听状态:")
    print(port_stdout or "(not listening)")

    print("\n--- 6. 读取最近 devserver 日志（仅查看） ---")
    log_stdout, log_stderr, _ = await run_cmd(
        sandbox, "bash -lc \"tail -n 120 /tmp/devserver.log 2>/dev/null || echo 'No /tmp/devserver.log found'\"",
    )
    safe_print(log_stdout or log_stderr or "(no log output)")

    print("\n--- 7. 预览地址探测（仅查看） ---")
    try:
        host = sandbox.get_host(expected_port)
        print(f"https://{host}")
    except Exception as e:
        print(f"get_host({expected_port}) failed: {e}")

    if repair:
        print("\n--- 8. 执行修复流程（--repair） ---")
        if expected_port == 3000:
            fix_cfg_stdout, fix_cfg_stderr, _ = await run_cmd(
                sandbox,
                "bash -lc \"if [ -f /home/user/project/next.config.ts ]; then "
                "cp /home/user/project/next.config.ts /home/user/project/next.config.ts.bak 2>/dev/null || true; "
                "cat > /home/user/project/next.config.mjs <<'EOF'\n"
                "const nextConfig = {};\n"
                "export default nextConfig;\n"
                "EOF\n"
                "rm -f /home/user/project/next.config.ts; "
                "echo 'Renamed next.config.ts -> next.config.mjs'; "
                "else echo 'No next.config.ts found'; fi\"",
            )
            safe_print(fix_cfg_stdout or fix_cfg_stderr or "(no config change)")

        print("修复步骤: npm install (可能较慢)")
        ins_stdout, ins_stderr, ins_code = await run_cmd(
            sandbox, "bash -lc \"cd /home/user/project && npm install\"",
        )
        if ins_stdout:
            safe_print(ins_stdout[-2000:])
        if ins_stderr:
            safe_print(ins_stderr[-2000:])
        print(f"npm install exit_code={ins_code}")

        await run_cmd(sandbox, "bash -lc \"pkill -f 'next|vite' >/dev/null 2>&1 || true\"")
        await run_cmd(sandbox, "bash -lc \"rm -f /tmp/devserver.log || true\"")

        pid, bg_err = await run_cmd_bg(
            sandbox,
            f"bash -lc \"cd /home/user/project && {start_cmd} > /tmp/devserver.log 2>&1\"",
        )
        if bg_err:
            print(f"后台启动失败: {bg_err}")
        else:
            print(f"后台启动 PID: {pid or '(unknown)'}")

        await asyncio.sleep(6)
        post_repair_port, _, _ = await run_cmd(
            sandbox,
            f"bash -lc \"ss -tlnp | grep -E ':{expected_port}\\s' || true\"",
        )
        print(f"修复后端口 {expected_port} 状态:")
        print(post_repair_port or "(not listening)")

        rep_log_stdout, rep_log_stderr, _ = await run_cmd(
            sandbox,
            "bash -lc \"tail -n 120 /tmp/devserver.log 2>/dev/null || echo 'No /tmp/devserver.log found'\"",
        )
        print("修复后最新日志:")
        safe_print(rep_log_stdout or rep_log_stderr or "(no log output)")

    if start_server:
        print("\n--- 9. 手动启动（可选） ---")
        print("你开启了 --start，开始尝试启动 dev server ...")
        try:
            await sandbox.commands.run(
                f"bash -lc \"cd /home/user/project && {start_cmd} > /tmp/devserver.log 2>&1\"",
                background=True,
            )
            await asyncio.sleep(5)
            post_start_stdout, _, _ = await run_cmd(
                sandbox,
                f"bash -lc \"ss -tlnp | grep -E ':{expected_port}\\s' || true\"",
            )
            print(f"启动后端口 {expected_port} 状态:")
            print(post_start_stdout or "(not listening)")
        except Exception as e:
            print(f"启动失败: {e}")

    print("\n检查完成。")


async def pick_running_sandbox_id() -> str | None:
    """Pick one running sandbox ID from E2B list API."""
    from e2b import AsyncSandbox

    print("正在查找正在运行的 Sandbox...")
    try:
        paginator = AsyncSandbox.list()
        while paginator.has_next:
            sandboxes = await paginator.next_items()
            for sb in sandboxes:
                sandbox_id = getattr(sb, "sandbox_id", None) or getattr(sb, "id", None)
                if sandbox_id:
                    return str(sandbox_id)
    except Exception as e:
        print(f"Error fetching sandboxes: {e}")
        return None
    return None


async def main() -> None:
    args = sys.argv[1:]
    start_server = "--start" in args
    repair = "--repair" in args
    args = [a for a in args if a not in {"--start", "--repair"}]

    arg_sandbox_id = args[0] if args else None
    if not arg_sandbox_id:
        arg_sandbox_id = await pick_running_sandbox_id()
    if not arg_sandbox_id:
        print("未找到可用 sandbox。请传入 sandbox_id，例如：")
        print("  uv run python tests/check_sandbox.py <sandbox_id> [--start] [--repair]")
        raise SystemExit(1)
    await check(arg_sandbox_id, start_server=start_server, repair=repair)


if __name__ == "__main__":
    asyncio.run(main())
