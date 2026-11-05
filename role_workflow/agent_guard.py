from pathlib import Path
from typing import Mapping

from role_workflow.agent_defs import find_agent_model
from role_workflow.decision import Refusal
from role_workflow.messages import agent_refusal


def _explicit(model: object) -> bool:
    return isinstance(model, str) and model.strip() != "" and model.strip().lower() != "inherit"


def check_agent_call(
    tool_input: Mapping, cwd: Path, config_dir: Path, plugin_root: Path
) -> Refusal | None:
    raw_type = tool_input.get("subagent_type")
    subagent_type = raw_type if isinstance(raw_type, str) and raw_type else None
    if subagent_type == "fork":
        return None
    model = tool_input.get("model")
    # A call-level model overrides the definition, so "inherit" here runs on the parent's model.
    if isinstance(model, str) and model.strip().lower() == "inherit":
        return Refusal(agent_refusal(subagent_type))
    if _explicit(model):
        return None
    if _explicit(find_agent_model(subagent_type or "general-purpose", cwd, config_dir, plugin_root)):
        return None
    return Refusal(agent_refusal(subagent_type))
