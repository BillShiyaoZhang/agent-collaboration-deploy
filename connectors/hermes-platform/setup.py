"""Refuse installation of the retired deployment-repository connector."""

raise SystemExit(
    "RETIRED: do not install connectors/hermes-platform from the deployment repository.\n"
    "In the Python environment running Hermes Gateway, install the SDK package instead:\n"
    "  python -m pip install --upgrade /path/to/agent-comm-platform/agent-comm/connectors/hermes-platform\n"
    "Start the current local helper with your existing keys and mailbox.db. Configure "
    "platforms.agent_comm.extra.platform_url=http://127.0.0.1:45042, plugins.enabled and "
    "an explicit allow_from in the actual HERMES_HOME.\n"
    "Follow the SDK connectors/hermes-platform/README.md; do not use the old generic CLI."
)
