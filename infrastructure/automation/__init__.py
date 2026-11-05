"""
Helpers de automação importáveis em qualquer parte do projeto.
Automation helpers importable anywhere in the project.
"""
from infrastructure.automation import vision  # noqa: F401
from infrastructure.automation import gui      # noqa: F401
from infrastructure.automation.recorder import Recorder, Macro  # noqa: F401

__all__ = ["vision", "gui", "Recorder", "Macro"]
