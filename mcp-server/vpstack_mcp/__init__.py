"""vpstack-mcp: MCP server exposing VP2026 voice-privacy tools to any MCP-aware AI agent."""
from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("vpstack-mcp")
except PackageNotFoundError:
    __version__ = "0.1.0.dev0"
