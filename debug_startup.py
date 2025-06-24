#!/usr/bin/env python3
import logging
import os
import sys

# Set up logging to stderr
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", stream=sys.stderr)

logger = logging.getLogger(__name__)

try:
    logger.info(f"Python: {sys.executable}")
    logger.info(f"CWD: {os.getcwd()}")
    logger.info(f"PATH: {sys.path[:3]}...")

    from odoo_intelligence_mcp.server import main

    logger.info("Import successful, calling main()...")
    main()
except Exception as e:
    logger.error(f"Error during startup: {e}", exc_info=True)
    sys.exit(1)
