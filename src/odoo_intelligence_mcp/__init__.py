from importlib.metadata import version

from .server import main

__version__ = version("odoo-intelligence-mcp")
__all__ = ["main"]
