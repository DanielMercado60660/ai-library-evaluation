"""Inbound Loan Workflow - SequentialAgent for multi-step inbound loan processing.

This workflow processes inbound loan requests from partner libraries:
1. Fetch pending inbound loan queue
2. Check book availability for each request
3. Evaluate against lending policy rules
4. Execute approval/denial decisions
5. Reserve approved items
"""

import logging
from typing import Any, Optional

from google.adk.agents import SequentialAgent, LlmAgent

from agents.config import MODEL_NAME
from agents.mcp.connection_manager import MCPConnectionManager, create_ill_toolset, create_catalog_toolset

logger = logging.getLogger(__name__)


# Agent instructions for each workflow step

FETCH_QUEUE_INSTRUCTION = """
You are the Queue Fetcher step in the Inbound Loan Workflow.

Your job is to fetch the pending inbound loan queue from the ILL service.

Steps:
1. Call get_pending_inbound_queue to retrieve all pending loan requests
2. Store the results in the session state under 'pending_loans'
3. Report how many loan requests were found

Output the count of pending loans and any relevant summary information.
"""

CHECK_AVAILABILITY_INSTRUCTION = """
You are the Availability Checker step in the Inbound Loan Workflow.

Your job is to check book availability for each pending loan request.

For each loan in {pending_loans}:
1. Extract the instance_id from the loan request
2. Call check_availability to get the instance status
3. Store availability info with the loan data

Store the enriched loan data with availability in 'loans_with_availability'.
"""

EVALUATE_INSTRUCTION = """
You are the Policy Evaluator step in the Inbound Loan Workflow.

Your job is to evaluate each loan request against lending policy rules.

For each loan in {loans_with_availability}:
1. Check if the instance is available
2. Review the requesting library's return rate
3. Apply policy rules:
   - Auto-Approve: Available + reliable library (>=90%) + multiple copies
   - Auto-Deny: Unavailable OR poor return rate (<75%) OR last copy
   - Skip: Moderate conditions requiring manual review

Store your decisions in 'decisions' with format:
[{{"id": "...", "decision": "approve|deny|skip", "reason": "..."}}]
"""

EXECUTE_INSTRUCTION = """
You are the Decision Executor step in the Inbound Loan Workflow.

Your job is to execute the decisions made in the evaluation step.

For each decision in {decisions}:
- If decision is "approve":
  1. Call reserve_instance to reserve the book for the loan
  2. Call approve_inbound_loan with librarian_id="inbound-loan-agent"
- If decision is "deny": Call deny_inbound_loan with the reason
- If decision is "skip": Log for manual review (no action needed)

Store execution results in 'execution_results'.
Report a summary of actions taken.
"""


def create_inbound_loan_workflow(
    mcp_manager: Optional[MCPConnectionManager] = None,
) -> SequentialAgent:
    """Create an Inbound Loan Workflow using SequentialAgent.

    This workflow chains together multiple LlmAgents to process inbound
    loan requests in a structured, step-by-step manner.

    Args:
        mcp_manager: Optional MCP connection manager for tool access

    Returns:
        Configured SequentialAgent instance
    """
    # Create MCP toolsets
    ill_tools = create_ill_toolset(tool_filter=[
        "get_pending_inbound_queue",
        "approve_inbound_loan",
        "deny_inbound_loan",
    ])

    catalog_tools = create_catalog_toolset(tool_filter=[
        "check_availability",
        "reserve_instance",
        "get_books_by_stratum",
    ])

    # Step 1: Fetch pending loan queue
    fetch_agent = LlmAgent(
        model=MODEL_NAME,
        name="fetch_pending_loans",
        description="Fetches pending inbound loan requests from the queue",
        instruction=FETCH_QUEUE_INSTRUCTION,
        tools=[ill_tools],
        output_key="pending_loans",
    )

    # Step 2: Check availability for each request
    availability_agent = LlmAgent(
        model=MODEL_NAME,
        name="check_availability",
        description="Checks book availability for each loan request",
        instruction=CHECK_AVAILABILITY_INSTRUCTION,
        tools=[catalog_tools],
        output_key="loans_with_availability",
    )

    # Step 3: Evaluate each request against policy
    evaluate_agent = LlmAgent(
        model=MODEL_NAME,
        name="evaluate_loans",
        description="Evaluates each loan request against lending policy",
        instruction=EVALUATE_INSTRUCTION,
        tools=[],  # No tools needed for pure evaluation
        output_key="decisions",
    )

    # Step 4: Execute decisions
    execute_agent = LlmAgent(
        model=MODEL_NAME,
        name="execute_decisions",
        description="Executes approval/denial decisions and reserves items",
        instruction=EXECUTE_INSTRUCTION,
        tools=[ill_tools, catalog_tools],
        output_key="execution_results",
    )

    # Create the sequential workflow
    workflow = SequentialAgent(
        name="inbound_loan_workflow",
        description="Multi-step inbound loan workflow that fetches, checks availability, evaluates, and executes lending decisions",
        sub_agents=[fetch_agent, availability_agent, evaluate_agent, execute_agent],
    )

    logger.info("Created Inbound Loan Workflow with SequentialAgent")
    return workflow


class InboundLoanWorkflow:
    """Wrapper class for the Inbound Loan SequentialAgent workflow.

    Provides a convenient interface for running the workflow and
    accessing results.
    """

    def __init__(self, mcp_manager: Optional[MCPConnectionManager] = None):
        """Initialize the workflow.

        Args:
            mcp_manager: Optional MCP connection manager
        """
        self._workflow = create_inbound_loan_workflow(mcp_manager)
        self._mcp_manager = mcp_manager

    @property
    def workflow(self) -> SequentialAgent:
        """Get the underlying SequentialAgent."""
        return self._workflow

    async def run(self, session_state: Optional[dict] = None) -> dict:
        """Run the complete inbound loan workflow.

        Args:
            session_state: Optional initial session state

        Returns:
            Workflow results including:
            - pending_loans: List of loan requests that were processed
            - loans_with_availability: Loans enriched with availability data
            - decisions: List of decisions made
            - execution_results: Results of executing decisions
        """
        try:
            logger.info("Starting Inbound Loan Workflow")

            # Initialize session state if needed
            state = session_state or {}

            # Run the workflow
            result = await self._workflow.run(input="Process pending inbound loan queue")

            # Extract results from session state
            return {
                "pending_loans": state.get("pending_loans", []),
                "loans_with_availability": state.get("loans_with_availability", []),
                "decisions": state.get("decisions", []),
                "execution_results": state.get("execution_results", []),
                "workflow_output": result,
            }

        except Exception as e:
            logger.error(f"Inbound Loan Workflow error: {e}")
            return {
                "error": str(e),
                "pending_loans": [],
                "loans_with_availability": [],
                "decisions": [],
                "execution_results": [],
            }

    async def run_for_single_loan(self, loan: dict) -> dict:
        """Run the workflow for a single inbound loan request.

        Args:
            loan: The loan request to process

        Returns:
            Processing result for this loan
        """
        initial_state = {
            "pending_loans": [loan],
        }
        return await self.run(session_state=initial_state)
