"""
UI Agents - Agents for deep-agents-ui automation
================================================

This package contains agents specialized for UI automation
and testing of the deep-agents-ui Next.js application.

Available agents:
- grok_ui_orchestrator: Main orchestrator with sub-agent support
"""

from .grok_ui_orchestrator import agent, create_worker_subagent

__all__ = ["agent", "create_worker_subagent"]
