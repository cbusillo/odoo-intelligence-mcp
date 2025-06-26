import logging
import sys
from pathlib import Path

# Set up logging to stderr
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", stream=sys.stderr)

logger = logging.getLogger(__name__)

try:
    logger.info(f"Python: {sys.executable}")
    logger.info(f"CWD: {Path.cwd()}")
    logger.info(f"PATH: {sys.path[:3]}...")

    from odoo_intelligence_mcp.server import main

    logger.info("Import successful, calling main()...")
    main()
except Exception as e:
    logger.exception("Error during startup")
    sys.exit(1)
