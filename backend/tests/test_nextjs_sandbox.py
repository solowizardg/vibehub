import asyncio
import logging
import os
import sys

# Add parent directory to path so we can import project modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from sandbox.e2b_backend import sandbox_manager

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

# Minimum files strictly required for a basic next.js app
FILES = {
    "package.json": """{
  "name": "test-app",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev"
  },
  "dependencies": {
    "next": "14.2.5",
    "react": "18.2.0",
    "react-dom": "18.2.0"
  }
}""",
    "app/page.js": """export default function Home() {
  return <h1>Hello from Next.js inside E2B Sandbox!</h1>
}""",
    "app/layout.js": """export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}""",
}


async def main():
    if not settings.e2b_api_key:
        logger.error("No E2B_API_KEY found in .env")
        return

    session_id = "test-session-123"
    
    logger.info("1. Creating Sandbox...")
    sandbox_id = await sandbox_manager.create_sandbox(session_id)
    logger.info(f"Sandbox ID: {sandbox_id}")
    
    try:
        logger.info("2. Writing files...")
        await sandbox_manager.write_files(session_id, FILES)
        
        logger.info("3. Running npm install...")
        install_res = await sandbox_manager.execute_command(session_id, "npm install")
        print(install_res["stdout"] or install_res["stderr"])
        if install_res["exit_code"] != 0:
            logger.error("npm install failed, skip starting dev server.")
            return
        
        logger.info("4. Starting Next.js Dev Server (npx next dev -H 0.0.0.0 -p 3000)...")
        # Ensure we pass the right command just like sandbox_execution.py
        await sandbox_manager.run_background(session_id, "npx next dev -H 0.0.0.0 -p 3000")
        
        logger.info("5. Waiting for port 3000 to open...")
        url = None
        for i in range(15):
            await asyncio.sleep(2)
            if await sandbox_manager.is_port_open(session_id, 3000):
                url = await sandbox_manager.get_preview_url(session_id, 3000)
                await sandbox_manager.extend_timeout(session_id, 3600)
                break
            print(f"Waiting... ({i+1}/15)")
            
        if url:
            logger.info(f"SUCCESS! Preview URL: {url}")
            logger.info("Sandbox is kept alive for 15 minutes. You can check it in E2B dashboard.")
            logger.info(f"Go to E2B dashboard -> Sandboxes -> {sandbox_id} to view it.")
        else:
            logger.error("Failed to start server. Logs:")
            # try to get logs if any
            res = await sandbox_manager.execute_command(session_id, "cat /home/user/project/.next/server/pages-manifest.json || echo 'No logs'")
            print(res)

    except Exception as e:
        logger.exception(e)
    # Intentionally NOT cleaning up so you can inspect it in the E2B dashboard
    # await sandbox_manager.cleanup(session_id)


if __name__ == "__main__":
    asyncio.run(main())
