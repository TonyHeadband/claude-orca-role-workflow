---
description: Check that role-workflow's hooks, role agents and session guidance are active
---

Run this with the Bash tool:

```
bash "${CLAUDE_PLUGIN_ROOT}/hooks/run-python" doctor --cwd "$PWD"
```

Show the output verbatim. Then, for each `[FAIL]` line, explain its `fix:` in one sentence. Change nothing yourself: do not delete, edit or install anything; leave the fixes to the user.
