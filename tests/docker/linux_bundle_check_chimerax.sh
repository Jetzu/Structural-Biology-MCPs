#!/usr/bin/env bash
# Inside the Linux container: install the bundle with the installer, then launch ChimeraX plainly and
# check that the bundle auto-started the bridge and registered the `agent` commands.
set -u
cd "$(dirname "$0")/../.."
.venv/bin/python -m molmcp.install --chimerax 2>&1 | grep -E "installed|failed"
rm -f "$MOLMCP_HOME"/instances/chimerax-*.json
echo "== plain --nogui launch, then 'agent status' and 'usage claude'"
ChimeraX --nogui --exit --cmd "agent status ; usage claude" 2>&1 | grep -iE "agent bridge|claude|Unknown|Error" | head -4
echo "== bridge instance files written by autostart (removed again on exit):"
ls "$MOLMCP_HOME"/instances/ 2>/dev/null; echo "(exit cleans the file; a bridge line above proves autostart)"
