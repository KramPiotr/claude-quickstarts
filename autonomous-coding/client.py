"""
Claude SDK Client Configuration
===============================

Functions for creating and configuring the Claude Agent SDK client.
"""

import json
import os
from pathlib import Path

from claude_code_sdk import ClaudeCodeOptions, ClaudeSDKClient
from claude_code_sdk.types import HookMatcher

from security import bash_security_hook


# Puppeteer MCP tools for browser automation
PUPPETEER_TOOLS = [
    "mcp__puppeteer__puppeteer_navigate",
    "mcp__puppeteer__puppeteer_screenshot",
    "mcp__puppeteer__puppeteer_click",
    "mcp__puppeteer__puppeteer_fill",
    "mcp__puppeteer__puppeteer_select",
    "mcp__puppeteer__puppeteer_hover",
    "mcp__puppeteer__puppeteer_evaluate",
]

# Built-in tools
BUILTIN_TOOLS = [
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
    "Bash",
]


def get_api_key() -> str:
    """
    Get the API key from environment variables.

    Checks for ANTHROPIC_API_KEY first, then falls back to CLAUDE_CODE_OAUTH_TOKEN.
    Both work with the Claude API.

    Returns:
        The API key string

    Raises:
        ValueError: If neither environment variable is set
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get(
        "CLAUDE_CODE_OAUTH_TOKEN"
    )
    if not api_key:
        raise ValueError(
            "Neither ANTHROPIC_API_KEY nor CLAUDE_CODE_OAUTH_TOKEN environment variable is set.\n"
            "Get your API key from: https://console.anthropic.com/\n"
            "Or use your Claude Code OAuth token."
        )
    return api_key


def setup_cli_path() -> str | None:
    """
    Ensure Claude CLI is findable by the SDK.

    The SDK uses shutil.which("claude") to find the CLI. This function adds
    preferred Claude installation directories to the FRONT of PATH so they
    take priority over system installations.

    Priority order:
    1. CLAUDE_CLI_PATH env var (if set)
    2. ~/.claude/local/claude (local installation, preferred)
    3. Other common locations
    4. System PATH (homebrew, etc.)

    Returns:
        Path to Claude CLI if found, None otherwise
    """
    import shutil

    # Preferred Claude CLI locations (in priority order)
    cli_locations = [
        Path.home() / ".claude" / "local",  # Local Claude installation (preferred)
        Path.home() / ".npm-global" / "bin",
        Path.home() / "node_modules" / ".bin",
    ]

    # Check CLAUDE_CLI_PATH env var - highest priority
    if cli_path_env := os.environ.get("CLAUDE_CLI_PATH"):
        cli_dir = Path(cli_path_env).parent
        cli_locations.insert(0, cli_dir)

    # Add directories containing claude binary to FRONT of PATH
    # This ensures our preferred locations take priority over system installs
    for location in cli_locations:
        claude_path = location / "claude"
        if claude_path.exists():
            # Prepend to PATH so it takes priority
            current_path = os.environ.get("PATH", "")
            if str(location) not in current_path:
                os.environ["PATH"] = f"{location}:{current_path}"
            return str(claude_path)

    # Fall back to whatever is in PATH
    if shutil.which("claude"):
        return shutil.which("claude")

    return None


def create_client(project_dir: Path, model: str) -> ClaudeSDKClient:
    """
    Create a Claude Agent SDK client with all tools enabled.

    Args:
        project_dir: Directory for the project
        model: Claude model to use

    Returns:
        Configured ClaudeSDKClient

    Note: Security checks disabled - all tools and commands are allowed.
    """
    api_key = get_api_key()

    # Security settings - all tools allowed without restrictions
    security_settings = {
        "sandbox": {"enabled": False},
        "permissions": {
            "defaultMode": "acceptEdits",
            "allow": [
                # Allow all file operations anywhere
                "Read(**)",
                "Write(**)",
                "Edit(**)",
                "Glob(**)",
                "Grep(**)",
                # All bash commands allowed
                "Bash(*)",
                # Allow Puppeteer MCP tools for browser automation
                *PUPPETEER_TOOLS,
            ],
        },
    }

    # Ensure project directory exists before creating settings file
    project_dir.mkdir(parents=True, exist_ok=True)

    # Write settings to a file in the project directory
    settings_file = project_dir / ".claude_settings.json"
    with open(settings_file, "w") as f:
        json.dump(security_settings, f, indent=2)

    print(f"Created settings at {settings_file}")
    print("   - Sandbox disabled (all system access allowed)")
    print("   - Filesystem: unrestricted")
    print("   - Bash commands: all allowed")
    print("   - MCP servers: puppeteer (browser automation)")
    print()

    # Ensure Claude CLI is findable (adds to PATH if needed)
    cli_path = setup_cli_path()
    if cli_path:
        print(f"   - Using Claude CLI at: {cli_path}")
    else:
        print("   - Warning: Claude CLI not found, SDK will attempt to locate it")

    return ClaudeSDKClient(
        options=ClaudeCodeOptions(
            model=model,
            system_prompt="You are an expert full-stack developer building a production-quality web application.",
            allowed_tools=[
                *BUILTIN_TOOLS,
                *PUPPETEER_TOOLS,
            ],
            mcp_servers={
                "puppeteer": {"command": "npx", "args": ["puppeteer-mcp-server"]}
            },
            hooks={
                "PreToolUse": [
                    HookMatcher(matcher="Bash", hooks=[bash_security_hook]),
                ],
            },
            max_turns=1000,
            cwd=str(project_dir.resolve()),
            settings=str(settings_file.resolve()),  # Use absolute path
        )
    )
