#!/usr/bin/env python3
"""
Create E2B sandbox templates with custom resource configuration.

Usage:
    python create_e2b_template.py --name "vibehub-react-vite" --dockerfile ../templates/react-vite/Dockerfile
    python create_e2b_template.py --name "vibehub-nextjs" --dockerfile ../templates/nextjs/Dockerfile
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Create E2B sandbox template")
    parser.add_argument("--name", required=True, help="Template name (e.g., vibehub-react-vite)")
    parser.add_argument("--dockerfile", required=True, help="Path to Dockerfile")
    parser.add_argument("--memory", type=int, default=4096, help="Memory in MB (default: 4096)")
    parser.add_argument("--vcpu", type=int, default=4, help="vCPU count (default: 4)")
    parser.add_argument("--timeout", type=int, default=3600, help="Default timeout in seconds (default: 3600)")
    parser.add_argument("--api-key", help="E2B API key (or set E2B_API_KEY env var)")
    return parser.parse_args()


async def create_template(args):
    """Create E2B template with specified configuration."""
    try:
        from e2b import AsyncSandbox
        from config import settings
    except ImportError as e:
        logger.error(f"Failed to import required modules: {e}")
        logger.error("Make sure you're in the backend directory and have installed dependencies")
        sys.exit(1)

    api_key = args.api_key or settings.e2b_api_key
    if not api_key:
        logger.error("E2B API key not found. Provide --api-key or set E2B_API_KEY in .env")
        sys.exit(1)

    dockerfile_path = Path(args.dockerfile)
    if not dockerfile_path.exists():
        logger.error(f"Dockerfile not found: {dockerfile_path}")
        sys.exit(1)

    dockerfile_content = dockerfile_path.read_text(encoding="utf-8")

    logger.info(f"Creating E2B template: {args.name}")
    logger.info(f"  Memory: {args.memory} MB ({args.memory / 1024:.1f} GB)")
    logger.info(f"  vCPU: {args.vcpu} cores")
    logger.info(f"  Timeout: {args.timeout}s")
    logger.info(f"  Dockerfile: {dockerfile_path}")

    try:
        # Create template using E2B SDK
        template = await AsyncSandbox.create_template(
            dockerfile=dockerfile_content,
            template_name=args.name,
            api_key=api_key,
            memory_mb=args.memory,
            vcpu_count=args.vcpu,
            timeout=args.timeout,
        )

        template_id = getattr(template, "template_id", None) or getattr(template, "id", None)

        logger.info(f"✅ Template created successfully!")
        logger.info(f"   Template ID: {template_id}")
        logger.info(f"   Name: {args.name}")
        logger.info(f"")
        logger.info(f"Add this to your backend/.env file:")

        if "react" in args.name.lower() and "vite" in args.name.lower():
            logger.info(f"   E2B_TEMPLATE_REACT_VITE={template_id}")
        elif "next" in args.name.lower():
            logger.info(f"   E2B_TEMPLATE_NEXTJS={template_id}")
        else:
            logger.info(f"   # Update config.py or .env with:")
            logger.info(f"   # Template {args.name} = {template_id}")

        return template_id

    except Exception as e:
        logger.error(f"Failed to create template: {e}")
        raise


def main():
    args = parse_args()
    asyncio.run(create_template(args))


if __name__ == "__main__":
    main()
