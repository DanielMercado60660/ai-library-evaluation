"""Checkout Workflow - SequentialAgent for multi-step checkout processing.

This workflow handles the complete checkout process:
1. Verify patron eligibility
2. Check book availability
3. Execute checkout
4. Generate confirmation and due date
"""

import logging
from typing import Any, Optional

from google.adk.agents import SequentialAgent, LlmAgent

from agents.config import MODEL_NAME
from agents.mcp.connection_manager import MCPConnectionManager, create_catalog_toolset, create_circulation_toolset

logger = logging.getLogger(__name__)


# Agent instructions for each workflow step

VERIFY_PATRON_INSTRUCTION = """
You are the Patron Verifier step in the Checkout Workflow.

Your job is to verify that the patron is eligible for checkout.

Given the patron_id in {checkout_request}:
1. Call get_patron_summary to get the patron's account status
2. Check for any blocks or excessive fines (>$10)
3. Verify they haven't exceeded their checkout limit

Store the patron verification result in 'patron_status' with:
- eligible: boolean
- issues: list of any problems found
- current_checkouts: number of items currently checked out
- checkout_limit: their maximum allowed checkouts
"""

CHECK_AVAILABILITY_INSTRUCTION = """
You are the Availability Checker step in the Checkout Workflow.

Your job is to verify the requested item is available for checkout.

Given the book_id or instance_id in {checkout_request}:
1. If instance_id provided, call check_availability for that specific copy
2. If only book_id provided, search for any available instance
3. Verify the item isn't on hold for someone else

Store availability result in 'item_availability' with:
- is_available: boolean
- instance_id: the specific instance to checkout
- location: shelf location for pickup
- holds_waiting: number of holds on this book
"""

EXECUTE_CHECKOUT_INSTRUCTION = """
You are the Checkout Executor step in the Checkout Workflow.

Your job is to execute the checkout if all conditions are met.

Check {patron_status} and {item_availability}:
- If patron is NOT eligible: Do not proceed, explain why
- If item is NOT available: Do not proceed, suggest placing a hold

If both are OK:
1. Call checkout_item with the instance_id and patron_id
2. Store the checkout result in 'checkout_result'

The checkout result should include:
- success: boolean
- checkout_id: if successful
- due_date: when the item is due
- message: confirmation or error message
"""

CONFIRMATION_INSTRUCTION = """
You are the Confirmation Generator step in the Checkout Workflow.

Your job is to generate a friendly confirmation message for the patron.

Based on {checkout_result}:
- If successful: Congratulate them, provide the due date, remind about renewals
- If failed: Explain what went wrong and suggest alternatives

Store the final message in 'confirmation_message'.
"""


def create_checkout_workflow(
    mcp_manager: Optional[MCPConnectionManager] = None,
) -> SequentialAgent:
    """Create a Checkout Workflow using SequentialAgent.

    This workflow chains together multiple LlmAgents to process a
    checkout request in a structured, step-by-step manner.

    Args:
        mcp_manager: Optional MCP connection manager for tool access

    Returns:
        Configured SequentialAgent instance
    """
    # Create MCP toolsets
    catalog_tools = create_catalog_toolset(tool_filter=[
        "check_availability",
        "get_book_details",
    ])

    circulation_tools = create_circulation_toolset(tool_filter=[
        "get_patron_summary",
        "checkout_item",
        "place_hold",
    ])

    # Step 1: Verify patron eligibility
    verify_patron_agent = LlmAgent(
        model=MODEL_NAME,
        name="verify_patron",
        description="Verifies patron eligibility for checkout",
        instruction=VERIFY_PATRON_INSTRUCTION,
        tools=[circulation_tools],
        output_key="patron_status",
    )

    # Step 2: Check item availability
    check_availability_agent = LlmAgent(
        model=MODEL_NAME,
        name="check_availability",
        description="Checks if the requested item is available",
        instruction=CHECK_AVAILABILITY_INSTRUCTION,
        tools=[catalog_tools],
        output_key="item_availability",
    )

    # Step 3: Execute checkout
    execute_checkout_agent = LlmAgent(
        model=MODEL_NAME,
        name="execute_checkout",
        description="Executes the checkout transaction",
        instruction=EXECUTE_CHECKOUT_INSTRUCTION,
        tools=[circulation_tools],
        output_key="checkout_result",
    )

    # Step 4: Generate confirmation
    confirmation_agent = LlmAgent(
        model=MODEL_NAME,
        name="generate_confirmation",
        description="Generates a confirmation message for the patron",
        instruction=CONFIRMATION_INSTRUCTION,
        tools=[],  # No tools needed for message generation
        output_key="confirmation_message",
    )

    # Create the sequential workflow
    workflow = SequentialAgent(
        name="checkout_workflow",
        description="Multi-step checkout workflow that verifies patron, checks availability, executes checkout, and confirms",
        sub_agents=[
            verify_patron_agent,
            check_availability_agent,
            execute_checkout_agent,
            confirmation_agent,
        ],
    )

    logger.info("Created Checkout Workflow with SequentialAgent")
    return workflow


class CheckoutWorkflow:
    """Wrapper class for the Checkout SequentialAgent workflow.

    Provides a convenient interface for running the workflow and
    accessing results.
    """

    def __init__(self, mcp_manager: Optional[MCPConnectionManager] = None):
        """Initialize the workflow.

        Args:
            mcp_manager: Optional MCP connection manager
        """
        self._workflow = create_checkout_workflow(mcp_manager)
        self._mcp_manager = mcp_manager

    @property
    def workflow(self) -> SequentialAgent:
        """Get the underlying SequentialAgent."""
        return self._workflow

    async def run(
        self,
        patron_id: str,
        book_id: Optional[str] = None,
        instance_id: Optional[str] = None,
    ) -> dict:
        """Run the complete checkout workflow.

        Args:
            patron_id: The patron requesting checkout
            book_id: The book to checkout (optional if instance_id provided)
            instance_id: Specific instance to checkout (optional)

        Returns:
            Workflow results including:
            - patron_status: Patron eligibility status
            - item_availability: Item availability info
            - checkout_result: Checkout transaction result
            - confirmation_message: Final message for patron
        """
        if not book_id and not instance_id:
            return {
                "error": "Either book_id or instance_id must be provided",
                "success": False,
            }

        try:
            logger.info(f"Starting Checkout Workflow for patron {patron_id}")

            # Build checkout request
            checkout_request = {
                "patron_id": patron_id,
                "book_id": book_id,
                "instance_id": instance_id,
            }

            # Initialize session state
            state = {
                "checkout_request": checkout_request,
            }

            # Run the workflow
            result = await self._workflow.run(
                input=f"Process checkout for patron {patron_id}"
            )

            # Extract results from session state
            return {
                "success": state.get("checkout_result", {}).get("success", False),
                "patron_status": state.get("patron_status", {}),
                "item_availability": state.get("item_availability", {}),
                "checkout_result": state.get("checkout_result", {}),
                "confirmation_message": state.get("confirmation_message", ""),
                "workflow_output": result,
            }

        except Exception as e:
            logger.error(f"Checkout Workflow error: {e}")
            return {
                "error": str(e),
                "success": False,
                "patron_status": {},
                "item_availability": {},
                "checkout_result": {},
                "confirmation_message": f"An error occurred: {str(e)}",
            }

    async def checkout_book(self, patron_id: str, book_id: str) -> dict:
        """Convenience method to checkout a book by book_id.

        Args:
            patron_id: The patron requesting checkout
            book_id: The book to checkout

        Returns:
            Checkout result
        """
        return await self.run(patron_id=patron_id, book_id=book_id)

    async def checkout_instance(self, patron_id: str, instance_id: str) -> dict:
        """Convenience method to checkout a specific instance.

        Args:
            patron_id: The patron requesting checkout
            instance_id: The specific instance to checkout

        Returns:
            Checkout result
        """
        return await self.run(patron_id=patron_id, instance_id=instance_id)
