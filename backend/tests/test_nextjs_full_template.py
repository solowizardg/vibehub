"""
Test: deploy the FULL Next.js template (all dependencies + all source files)
into an E2B sandbox and start `next dev`.
"""
import asyncio
import logging
import os
import sys
import time

# Add parent directory to path so we can import project modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from sandbox.e2b_backend import sandbox_manager

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

# Resolve the nextjs template directory
TEMPLATE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "templates", "nextjs")
)

# Files/dirs to skip when collecting template files
SKIP = {
    "node_modules",
    ".next",
    "package-lock.json",
    ".git",
    "prompts",
    "meta.json",
    ".donttouch_files.json",
    ".important_files.json",
    ".gitignore",
}


def collect_template_files() -> dict[str, str]:
    """Walk the template directory and return {relative_path: contents}."""
    file_map: dict[str, str] = {}
    for root, dirs, files in os.walk(TEMPLATE_DIR):
        # Prune directories we want to skip
        dirs[:] = [d for d in dirs if d not in SKIP]

        for fname in files:
            if fname in SKIP:
                continue
            abs_path = os.path.join(root, fname)
            rel_path = os.path.relpath(abs_path, TEMPLATE_DIR).replace("\\", "/")

            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except (UnicodeDecodeError, OSError):
                logger.warning("Skipping non-text file: %s", rel_path)
                continue

            file_map[rel_path] = content
    return file_map


async def main():
    if not settings.e2b_api_key:
        logger.error("No E2B_API_KEY found in .env")
        return

    # Collect all template files
    file_map = collect_template_files()
    logger.info("Collected %d files from template: %s", len(file_map), TEMPLATE_DIR)
    for path in sorted(file_map.keys()):
        size = len(file_map[path])
        logger.info("  %s (%d bytes)", path, size)

    session_id = "test-nextjs-full-template"

    # 1. Create sandbox with custom template (Node.js + deps pre-installed)
    logger.info("1. Creating Sandbox with custom nextjs template...")
    t0 = time.perf_counter()
    from sandbox.e2b_backend import get_template_id
    sandbox_id = await sandbox_manager.create_sandbox(session_id, template=get_template_id("nextjs"))
    logger.info("   Sandbox ID: %s (%.1fs)", sandbox_id, time.perf_counter() - t0)

    try:
        # 2. Write files
        logger.info("2. Writing %d files to sandbox...", len(file_map))
        t0 = time.perf_counter()
        await sandbox_manager.write_files(session_id, file_map)
        logger.info("   Done (%.1fs)", time.perf_counter() - t0)

        # 3. npm install (should be fast since deps are pre-installed in template)
        logger.info("3. Running npm install (should be fast - deps pre-installed)...")
        t0 = time.perf_counter()
        install_res = await sandbox_manager.execute_command(
            session_id, "npm install", timeout=120
        )
        elapsed = time.perf_counter() - t0
        if install_res["stdout"]:
            # Print last 2000 chars to avoid too much noise
            print(install_res["stdout"][-2000:])
        if install_res["stderr"]:
            print(install_res["stderr"][-2000:])
        logger.info("   npm install exit_code=%d (%.1fs)", install_res["exit_code"], elapsed)
        if install_res["exit_code"] != 0:
            logger.error("npm install failed, aborting.")
            return

        # 4. Check memory
        logger.info("4. Checking sandbox memory...")
        mem_res = await sandbox_manager.execute_command(
            session_id,
            "free -m",
            timeout=10,
        )
        print(mem_res["stdout"])

        # 5. Start next dev (NO build step!)
        dev_cmd = "npx next dev -H 0.0.0.0 -p 3000"
        logger.info("5. Starting Next.js Dev Server: %s", dev_cmd)
        t0 = time.perf_counter()
        await sandbox_manager.run_background(
            session_id,
            f'bash -lc "cd /home/user/project && {dev_cmd} > /tmp/devserver.log 2>&1"',
        )

        # 6. Wait for port 3000
        logger.info("6. Waiting for port 3000 to open...")
        url = None
        for i in range(20):
            await asyncio.sleep(3)
            if await sandbox_manager.is_port_open(session_id, 3000):
                url = await sandbox_manager.get_preview_url(session_id, 3000)
                await sandbox_manager.extend_timeout(session_id, 3600)
                break
            # Check if process is still alive
            alive = await sandbox_manager.is_process_running(session_id, "next")
            status = "running" if alive else "DEAD"
            print(f"   Waiting... ({i + 1}/20) process={status}")

        elapsed = time.perf_counter() - t0
        if url:
            logger.info("SUCCESS! Preview URL: %s (%.1fs to start)", url, elapsed)
            logger.info("Sandbox kept alive. ID: %s", sandbox_id)
        else:
            logger.error("FAILED to start dev server after %.1fs", elapsed)

        # 7. Print dev server logs
        logger.info("7. Dev server logs:")
        log_res = await sandbox_manager.execute_command(
            session_id,
            "tail -n 60 /tmp/devserver.log 2>/dev/null || echo 'No log file'",
            timeout=10,
        )
        print(log_res["stdout"] or log_res["stderr"] or "(empty)")

        # 8. Check memory after startup
        logger.info("8. Memory after dev server start:")
        mem_res2 = await sandbox_manager.execute_command(
            session_id,
            "free -m",
            timeout=10,
        )
        print(mem_res2["stdout"])

    except Exception as e:
        logger.exception(e)


if __name__ == "__main__":
    asyncio.run(main())
