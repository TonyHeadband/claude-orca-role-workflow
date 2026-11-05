import re
import shlex
from typing import Literal, Mapping

from .decision import Refusal
from .messages import orca_refusal

_HEREDOC = re.compile(r"<<(?!<)(-?)\s*(?:'([^']+)'|\"([^\"]+)\"|([^\s;&|()<>'\"]+))")
_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
_PREFIXES = {"&", "command", "exec", "env"}
_LITERAL_ORCA = {"$ORCA_CLI_COMMAND", "${ORCA_CLI_COMMAND}", "$env:ORCA_CLI_COMMAND"}
_ORCA_NAMES = {"orca", "orca-ide", "orca-dev"}
_LAUNCH_FORMS = {
    ("orchestration", "worker-start"),
    ("agent", "launch"),
    ("worktree", "create"),
}
_SEPARATORS = ";&|()\n"


def _strip_heredocs(command: str) -> str:
    kept: list[str] = []
    delimiter = None
    strip_tabs = False
    for line in command.split("\n"):
        if delimiter is not None:
            body = line.lstrip("\t") if strip_tabs else line
            if body == delimiter:
                delimiter = None
            continue
        kept.append(line)
        match = _HEREDOC.search(line)
        if match:
            strip_tabs = match.group(1) == "-"
            delimiter = match.group(2) or match.group(3) or match.group(4)
    return "\n".join(kept)


def _split_commands(command: str) -> list[str]:
    """Split on shell separators, treating newlines as separators only outside quotes."""
    text = _strip_heredocs(command)
    commands: list[str] = []
    current: list[str] = []
    quote = None
    i = 0
    while i < len(text):
        ch = text[i]
        if quote:
            current.append(ch)
            if ch == "\\" and quote == '"' and i + 1 < len(text):
                i += 1
                current.append(text[i])
            elif ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
            current.append(ch)
        elif ch == "\\" and i + 1 < len(text):
            current.append(ch)
            i += 1
            current.append(text[i])
        elif ch in _SEPARATORS:
            commands.append("".join(current))
            current = []
        else:
            current.append(ch)
        i += 1
    commands.append("".join(current))
    return [c for c in commands if c.strip()]


def _is_orca(token: str, env: Mapping[str, str]) -> bool:
    if token in _LITERAL_ORCA:
        return True
    configured = env.get("ORCA_CLI_COMMAND")
    if configured and token == configured:
        return True
    name = re.split(r"[/\\]", token)[-1].lower()
    if name.endswith(".exe"):
        name = name[:-4]
    return name in _ORCA_NAMES


def _read_flags(tokens: list[str]) -> dict[str, str]:
    flags: dict[str, str] = {}
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.startswith("--") and len(token) > 2:
            if "=" in token:
                name, value = token.split("=", 1)
            elif i + 1 < len(tokens) and not tokens[i + 1].startswith("-"):
                name, value = token, tokens[i + 1]
                i += 1
            else:
                name, value = token, ""
            flags[name] = value
        i += 1
    return flags


def _launch_form(tokens: list[str], env: Mapping[str, str]) -> str | None:
    """Return the launch form if `tokens` is an Orca Claude launch without a model."""
    i = 0
    while i < len(tokens) and (_ASSIGNMENT.match(tokens[i]) or tokens[i] in _PREFIXES):
        i += 1
    if i >= len(tokens) or not _is_orca(tokens[i], env):
        return None
    rest = tokens[i + 1:]
    positional = [t for t in rest if not t.startswith("-")][:2]
    if tuple(positional) not in _LAUNCH_FORMS:
        return None
    flags = _read_flags(rest)
    if "--agent" not in flags:
        return None
    if positional[1] == "worker-start" and "--terminal" in flags:
        return None
    if flags["--agent"].lower() != "claude":
        return None
    if flags.get("--model"):
        return None
    return " ".join(positional)


def check_orca_command(
    command: str, shell: Literal["bash", "powershell"], env: Mapping[str, str]
) -> Refusal | None:
    try:
        if shell == "powershell":
            command = command.replace("\\", "/")
        for simple in _split_commands(command):
            lexer = shlex.shlex(simple, posix=True, punctuation_chars=True)
            lexer.whitespace_split = True
            form = _launch_form(list(lexer), env)
            if form:
                return Refusal(orca_refusal(form))
    except ValueError:
        return None
    return None
