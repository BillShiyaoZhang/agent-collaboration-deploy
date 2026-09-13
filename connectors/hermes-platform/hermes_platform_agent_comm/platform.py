"""Guard direct file loading as well as normal package imports."""

raise ImportError(
    "RETIRED: the deployment-repository AgentCommPlatform implementation was removed. "
    "Install the SDK package agent-comm-platform/agent-comm/connectors/hermes-platform "
    "in Hermes Gateway's Python environment. Connect it to the current local helper at "
    "http://127.0.0.1:45042 using platforms.agent_comm.extra.platform_url; "
    "follow the SDK connectors/hermes-platform/README.md."
)
