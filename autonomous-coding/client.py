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


def get_cli_path() -> str | None:
    """
    Get the Claude CLI path from environment variable or default location.

    Checks CLAUDE_CLI_PATH env var first, then falls back to ~/.claude/local/claude.

    Returns:
        Path to Claude CLI binary, or None to use SDK default search
    """
    # Check env var first
    cli_path = os.environ.get("CLAUDE_CLI_PATH")
    if cli_path:
        return cli_path

    # Check common location for local Claude installation
    home_claude = Path.home() / ".claude" / "local" / "claude"
    if home_claude.exists():
        return str(home_claude)

    # Let SDK find it
    return None


def create_client(project_dir: Path, model: str) -> ClaudeSDKClient:
    """
    Create a Claude Agent SDK client with multi-layered security.

    Args:
        project_dir: Directory for the project
        model: Claude model to use

    Returns:
        Configured ClaudeSDKClient

    Security layers (defense in depth):
    1. Sandbox - OS-level bash command isolation prevents filesystem escape
    2. Permissions - File operations restricted to project_dir only
    3. Security hooks - Bash commands validated against an allowlist
       (see security.py for ALLOWED_COMMANDS)
    """
    api_key = get_api_key()

    # Create comprehensive security settings
    # Note: Using relative paths ("./**") restricts access to project directory
    # since cwd is set to project_dir
    security_settings = {
        "sandbox": {"enabled": True, "autoAllowBashIfSandboxed": True},
        "permissions": {
            "defaultMode": "acceptEdits",  # Auto-approve edits within allowed directories
            "allow": [
                # Allow all file operations within the project directory
                "Read(./**)",
                "Write(./**)",
                "Edit(./**)",
                "Glob(./**)",
                "Grep(./**)",
                # Bash permission granted here, but actual commands are validated
                # by the bash_security_hook (see security.py for allowed commands)
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

    print(f"Created security settings at {settings_file}")
    print("   - Sandbox enabled (OS-level bash isolation)")
    print(f"   - Filesystem restricted to: {project_dir.resolve()}")
    print("   - Bash commands restricted to allowlist (see security.py)")
    print("   - MCP servers: puppeteer (browser automation)")
    print()

    # Get CLI path (supports custom installations like ~/.claude/local/claude)
    cli_path = get_cli_path()
    if cli_path:
        print(f"   - Using Claude CLI at: {cli_path}")

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
            cli_path=cli_path,
        )
    )
