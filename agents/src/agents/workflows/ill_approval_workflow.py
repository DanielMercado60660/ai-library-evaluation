"""ILL Approval Workflow - SequentialAgent for multi-step ILL approval.

This workflow processes ILL requests through a structured pipeline:
1. Fetch pending queue
2. Check patron eligibility for each request
3. Evaluate against policy rules
4. Execute approval/denial decisions
5. Record audit trail
"""

import logging
from typing import Any, Optional

from google.adk.agents import SequentialAgent, LlmAgent

from agents.config import MODEL_NAME
from agents.mcp.connection_manager import MCPConnectionManager, create_ill_toolset, create_circulation_toolset

logger = logging.getLogger(__name__)


# Agent instructions for each workflow step

FETCH_QUEUE_INSTRUCTION = """
You are the Queue Fetcher step in the ILL Approval Workflow.

Your job is to fetch the pending outbound approval queue from the ILL service.

Steps:
1. Call get_pending_outbound_queue to retrieve all pending requests
2. Store the results in the session state under 'pending_requests'
3. Report how many requests were found

Output the count of pending requests and any relevant summary information.
"""

EVALUATE_INSTRUCTION = """
You are the Policy Evaluator step in the ILL Approval Workflow.

Your job is to evaluate each pending ILL request against policy rules.

For each request in {pending_requests}:
1. Check patron eligibility using check_patron_eligibility
2. Review the library context (fulfillment rate, active status)
3. Apply policy rules:
   - Auto-Approve: Good patron (<$5 fines) + reliable library (>=85%)
   - Auto-Deny: Blocked patron OR fines >=10 OR library <70%
   - Skip: Moderate conditions requiring manual review

Store your decisions in 'decisions' with format:
[{{"id": "...", "decision": "approve|deny|skip", "reason": "..."}}]
"""

EXECUTE_INSTRUCTION = """
You are the Decision Executor step in the ILL Approval Workflow.

Your job is to execute the decisions made in the evaluation step.

For each decision in {decisions}:
- If decision is "approve": Call approve_ill_request with librarian_id="ill-approval-agent"
- If decision is "deny": Call deny_ill_request with the reason
- If decision is "skip": Log for manual review (no action needed)

Store execution results in 'execution_results'.
Report a summary of actions taken.
"""


def create_ill_approval_workflow(
    mcp_manager: Optional[MCPConnectionManager] = None,
) -> SequentialAgent:
    """Create an ILL Approval Workflow using SequentialAgent.

    This workflow chains together multiple LlmAgents to process ILL requests
    in a structured, step-by-step manner with state passing between steps.

    Args:
        mcp_manager: Optional MCP connection manager for tool access

    Returns:
        Configured SequentialAgent instance
    """
    # Create MCP toolsets
    ill_tools = create_ill_toolset(tool_filter=[
        "get_pending_outbound_queue",
        "approve_ill_request",
        "deny_ill_request",
        "query_audit_trail",
    ])

    circulation_tools = create_circulation_toolset(tool_filter=[
        "check_patron_eligibility",
        "calculate_patron_fines",
    ])

    # Step 1: Fetch pending queue
    fetch_agent = LlmAgent(
        model=MODEL_NAME,
        name="fetch_pending_queue",
        description="Fetches pending ILL requests from the approval queue",
        instruction=FETCH_QUEUE_INSTRUCTION,
        tools=[ill_tools],
        output_key="pending_requests",
    )

    # Step 2: Evaluate each request against policy
    evaluate_agent = LlmAgent(
        model=MODEL_NAME,
        name="evaluate_requests",
        description="Evaluates each request against ILL approval policy",
        instruction=EVALUATE_INSTRUCTION,
        tools=[circulation_tools],
        output_key="decisions",
    )

    # Step 3: Execute decisions
    execute_agent = LlmAgent(
        model=MODEL_NAME,
        name="execute_decisions",
        description="Executes approval/denial decisions",
        instruction=EXECUTE_INSTRUCTION,
        tools=[ill_tools],
        output_key="execution_results",
    )

    # Create the sequential workflow
    workflow = SequentialAgent(
        name="ill_approval_workflow",
        description="Multi-step ILL approval workflow that fetches, evaluates, and executes approval decisions",
        sub_agents=[fetch_agent, evaluate_agent, execute_agent],
    )

    logger.info("Created ILL Approval Workflow with SequentialAgent")
    return workflow


class ILLApprovalWorkflow:
    """Wrapper class for the ILL Approval SequentialAgent workflow.

    Provides a convenient interface for running the workflow and
    accessing results.
    """

    def __init__(self, mcp_manager: Optional[MCPConnectionManager] = None):
        """Initialize the workflow.

        Args:
            mcp_manager: Optional MCP connection manager
        """
        self._workflow = create_ill_approval_workflow(mcp_manager)
        self._mcp_manager = mcp_manager

    @property
    def workflow(self) -> SequentialAgent:
        """Get the underlying SequentialAgent."""
        return self._workflow

    async def run(self, session_state: Optional[dict] = None) -> dict:
        """Run the complete ILL approval workflow.

        Args:
            session_state: Optional initial session state

        Returns:
            Workflow results including:
            - pending_requests: List of requests that were processed
            - decisions: List of decisions made
            - execution_results: Results of executing decisions
        """
        try:
            logger.info("Starting ILL Approval Workflow")

            # Initialize session state if needed
            state = session_state or {}

            # Run the workflow
            result = await self._workflow.run(input="Process pending ILL approval queue")

            # Extract results from session state
            return {
                "pending_requests": state.get("pending_requests", []),
                "decisions": state.get("decisions", []),
                "execution_results": state.get("execution_results", []),
                "workflow_output": result,
            }

        except Exception as e:
            logger.error(f"ILL Approval Workflow error: {e}")
            return {
                "error": str(e),
                "pending_requests": [],
                "decisions": [],
                "execution_results": [],
            }

    async def run_for_single_request(self, request: dict) -> dict:
        """Run the workflow for a single ILL request.

        Args:
            request: The ILL request to process

        Returns:
            Processing result for this request
        """
        # For single requests, we can use a simpler approach
        initial_state = {
            "pending_requests": [request],
        }
        return await self.run(session_state=initial_state)
