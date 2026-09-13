"""Compatibility guard for imports from the retired deployment package."""

raise ImportError(
    "RETIRED: this deployment-repository Hermes connector cannot use the current protocol. "
    "Install agent-comm-platform/agent-comm/connectors/hermes-platform in Hermes Gateway's "
    "Python environment and remove the old duplicate installation from that environment. "
    "Use platforms.agent_comm.extra.platform_url=http://127.0.0.1:45042 with the local helper. "
    "See the SDK connectors/hermes-platform/README.md for migration and identity preservation."
)
