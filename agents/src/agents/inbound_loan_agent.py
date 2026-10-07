"""Inbound Loan Agent - Automated approval/denial of lending requests from partner libraries.

This agent uses Google ADK (Agent Development Kit) to process inbound loan requests.
It connects to MCP servers for direct database access to:
- ILL service (inbound loan queues, approval management)
- Catalog service (book availability, instance status)

The agent applies lending policy rules to make decisions about loaning our books.
"""

import json
import logging
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

from agents.models.factory import build_model_adapter

logger = logging.getLogger(__name__)


# Policy rules for inbound loan decisions
INBOUND_LOAN_POLICY = """
## Inbound Loan Policy Rules

You are an automated Inbound Loan Agent for the Hanno Memorial Library.
Your job is to review incoming loan requests from partner libraries and decide whether to lend our books.

### Auto-Approve Criteria (approve immediately):
1. Requested instance is available
2. Requesting library has on-time return rate >= 90%
3. Book is not a rare or restricted item (stratum != 1 for Noble Tragedies unless common)
4. We have multiple copies available (total_copies > 1 AND available > 0)

### Auto-Deny Criteria (deny immediately):
1. Requested instance is not available (checked out, on hold, or reserved)
2. Requesting library has on-time return rate < 75%
3. Book is a rare item with only 1 copy
4. Requesting library is not in active status

### Manual Review Required:
1. On-time return rate between 75% and 90%
2. Last copy of a popular book
3. Stratum I (Noble Tragedies) books
4. Any edge cases not covered by above rules

### Decision Process:
1. First, get the pending inbound loan queue
2. For each loan request:
   a. Check instance availability using the catalog MCP tools
   b. Review the library context (return rates, status)
   c. Apply the policy rules above
   d. Make a decision: approve, deny, or skip (manual review)
   e. For approvals: call approve_inbound_loan with your librarian_id
   f. For denials: call deny_inbound_loan with a clear reason
3. Log all decisions with reasoning

### Important:
- Your librarian_id for all actions is: "inbound-loan-agent"
- Always provide clear notes explaining your decision
- Protect rare items (Stratum I, single copies)
- Consider local patron demand before lending
- If unsure, skip the request for manual review
"""


def create_inbound_loan_agent(
    ill_mcp_path: str | None = None,
    catalog_mcp_path: str | None = None,
) -> LlmAgent:
    """Create an Inbound Loan Agent with MCP tool access.

    Args:
        ill_mcp_path: Path to the ILL MCP server script
        catalog_mcp_path: Path to the Catalog MCP server script

    Returns:
        Configured LlmAgent instance
    """
    tools = []

    # Default paths if not provided (for Docker deployment)
    if ill_mcp_path is None:
        ill_mcp_path = "/app/services/ill/src/ill/mcp_server.py"
    if catalog_mcp_path is None:
        catalog_mcp_path = "/app/services/catalog/src/catalog/mcp_server.py"

    # Add ILL MCP toolset
    try:
        ill_toolset = McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command="python",
                    args=["-m", "ill.mcp_server"],
                    env={
                        "DATABASE_URL": "sqlite:///./db/ill.db",
                        "PYTHONPATH": "/app/services/ill/src:/app/shared/src"
                    }
                )
            ),
            tool_filter=[
                "approve_inbound_loan",
                "deny_inbound_loan",
                "get_queue_statistics",
            ]
        )
        tools.append(ill_toolset)
        logger.info("ILL MCP toolset configured for inbound loans")
    except Exception as e:
        logger.warning(f"Failed to configure ILL MCP toolset: {e}")

    # Add Catalog MCP toolset
    try:
        catalog_toolset = McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command="python",
                    args=["-m", "catalog.mcp_server"],
                    env={
                        "DATABASE_URL": "sqlite:///./db/catalog.db",
                        "PYTHONPATH": "/app/services/catalog/src:/app/shared/src"
                    }
                )
            ),
            tool_filter=[
                "check_availability",
                "reserve_instance",
                "get_books_by_stratum",
            ]
        )
        tools.append(catalog_toolset)
        logger.info("Catalog MCP toolset configured")
    except Exception as e:
        logger.warning(f"Failed to configure Catalog MCP toolset: {e}")

    # Create the agent
    model_ref = build_model_adapter().to_adk_model_ref()
    agent = LlmAgent(
        model=model_ref,
        name="inbound_loan_agent",
        description="Automated inbound loan agent that reviews lending requests from partner libraries and makes decisions based on availability and policy rules.",
        instruction=INBOUND_LOAN_POLICY,
        tools=tools,
    )
    # Track toolsets on agent so callers can clean up MCP connections
    agent._mcp_toolsets = tools  # type: ignore[attr-defined]

    return agent


def evaluate_inbound_loan(
    loan: dict,
    book_availability: dict,
) -> tuple[str, str]:
    """Evaluate an inbound loan request against policy rules.

    Args:
        loan: The inbound loan data from the queue
        book_availability: Book availability check result

    Returns:
        Tuple of (decision, reason) where decision is 'approve', 'deny', or 'skip'
    """
    # Check instance availability
    if not book_availability.get("is_available", False):
        return ("deny", f"Instance not available - current status prevents lending")

    total_copies = book_availability.get("total_copies", 0)
    available_copies = book_availability.get("available_copies", 0)

    # Check library context
    library_context = loan.get("library_context", {})
    on_time_rate = library_context.get("on_time_return_rate")

    # Auto-deny: poor return rate
    if on_time_rate is not None and on_time_rate < 0.75:
        return ("deny", f"Requesting library has poor on-time return rate ({on_time_rate:.0%})")

    # Auto-deny: last copy
    if total_copies == 1:
        return ("deny", "Cannot lend last/only copy")

    # Check for rare items (Stratum I)
    # This would typically come from the book data
    # For now, we'll need the book stratum info from elsewhere

    # Auto-approve: good library, multiple copies available
    if on_time_rate is not None and on_time_rate >= 0.90:
        if available_copies >= 1 and total_copies > 1:
            return ("approve", "Reliable library, multiple copies available")

    # Manual review: moderate return rate
    if on_time_rate is not None and 0.75 <= on_time_rate < 0.90:
        return ("skip", f"Library return rate ({on_time_rate:.0%}) requires manual review")

    # Manual review: last available but not last total
    if available_copies == 1 and total_copies > 1:
        return ("skip", "Last available copy - manual review required")

    # Default to approval for good conditions
    if available_copies >= 1 and (on_time_rate is None or on_time_rate >= 0.90):
        return ("approve", "Book available, no policy concerns")

    # Default to manual review for edge cases
    return ("skip", "Edge case - manual review recommended")


class InboundLoanProcessor:
    """Processor for batch inbound loan processing using policy rules."""

    def __init__(self, ill_tools: dict, catalog_tools: dict):
        """Initialize the processor.

        Args:
            ill_tools: Dictionary of ILL MCP tool functions
            catalog_tools: Dictionary of Catalog MCP tool functions
        """
        self.ill_tools = ill_tools
        self.catalog_tools = catalog_tools
        self.agent_id = "inbound-loan-agent"

    async def _get_pending_queue(self) -> list[dict]:
        """Fetch the pending inbound loan queue.

        Returns:
            List of pending inbound loan requests
        """
        get_queue = self.ill_tools.get("get_pending_inbound_queue")
        if not get_queue:
            logger.warning("get_pending_inbound_queue tool not available")
            return []

        try:
            result = await get_queue()
            if isinstance(result, str):
                result = json.loads(result)
            return result.get("items", [])
        except Exception as e:
            logger.error(f"Error fetching pending inbound queue: {e}")
            return []

    async def _check_availability(self, instance_id: str) -> dict:
        """Check book instance availability.

        Args:
            instance_id: The instance ID to check

        Returns:
            Availability result dictionary
        """
        check_availability = self.catalog_tools.get("check_availability")
        if not check_availability:
            return {"is_available": False, "error": "Catalog tools not available"}

        try:
            result = await check_availability(instance_id)
            if isinstance(result, str):
                result = json.loads(result)
            return result
        except Exception as e:
            logger.error(f"Error checking availability: {e}")
            return {"is_available": False, "error": str(e)}

    async def _approve_loan(self, loan_id: str, reason: str) -> dict:
        """Approve an inbound loan request.

        Args:
            loan_id: The loan request ID to approve
            reason: Reason for approval

        Returns:
            Approval result
        """
        approve = self.ill_tools.get("approve_inbound_loan")
        if not approve:
            raise ValueError("approve_inbound_loan tool not available")

        return await approve(
            loan_id=loan_id,
            librarian_id=self.agent_id,
            notes=reason,
        )

    async def _deny_loan(self, loan_id: str, reason: str) -> dict:
        """Deny an inbound loan request.

        Args:
            loan_id: The loan request ID to deny
            reason: Reason for denial

        Returns:
            Denial result
        """
        deny = self.ill_tools.get("deny_inbound_loan")
        if not deny:
            raise ValueError("deny_inbound_loan tool not available")

        return await deny(
            loan_id=loan_id,
            librarian_id=self.agent_id,
            reason=reason,
        )

    async def _reserve_instance(self, instance_id: str, loan_id: str) -> dict:
        """Reserve an instance for an approved loan.

        Args:
            instance_id: The instance to reserve
            loan_id: The loan request ID

        Returns:
            Reservation result
        """
        reserve = self.catalog_tools.get("reserve_instance")
        if not reserve:
            logger.warning("reserve_instance tool not available")
            return {"success": False, "error": "Reserve tool not available"}

        try:
            return await reserve(
                instance_id=instance_id,
                reserved_for=f"ILL:{loan_id}",
            )
        except Exception as e:
            logger.error(f"Error reserving instance: {e}")
            return {"success": False, "error": str(e)}

    async def process_pending_queue(self) -> dict:
        """Process all pending inbound loan requests.

        Returns:
            Summary of processing results with structure:
            {
                "approved": [{"id": str, "reason": str, ...}, ...],
                "denied": [{"id": str, "reason": str, ...}, ...],
                "skipped": [{"id": str, "reason": str, ...}, ...],
                "errors": [{"id": str, "error": str}, ...],
                "total_processed": int,
            }
        """
        results = {
            "approved": [],
            "denied": [],
            "skipped": [],
            "errors": [],
            "total_processed": 0,
        }

        logger.info("Inbound Loan Processor started")
        logger.info(f"Agent ID: {self.agent_id}")

        # Fetch pending queue
        try:
            queue = await self._get_pending_queue()
            logger.info(f"Fetched {len(queue)} pending inbound loan requests")
        except Exception as e:
            logger.error(f"Failed to fetch pending queue: {e}")
            results["errors"].append({"id": "queue_fetch", "error": str(e)})
            return results

        # Process each loan request
        for loan in queue:
            loan_id = loan.get("id", "unknown")
            results["total_processed"] += 1

            try:
                # Get instance availability
                instance_id = loan.get("instance_id")
                if not instance_id:
                    results["skipped"].append({
                        "id": loan_id,
                        "reason": "Missing instance_id in loan request"
                    })
                    continue

                availability = await self._check_availability(instance_id)

                # Evaluate against policy rules
                decision, reason = evaluate_inbound_loan(loan, availability)

                # Execute decision
                if decision == "approve":
                    try:
                        # Reserve the instance first
                        reserve_result = await self._reserve_instance(instance_id, loan_id)

                        # Approve the loan
                        await self._approve_loan(loan_id, reason)
                        results["approved"].append({
                            "id": loan_id,
                            "reason": reason,
                            "instance_id": instance_id,
                            "requesting_library": loan.get("requesting_library_id"),
                            "reserved": reserve_result.get("success", False),
                        })
                        logger.info(f"Approved inbound loan {loan_id}: {reason}")
                    except Exception as e:
                        results["errors"].append({
                            "id": loan_id,
                            "error": f"Approval failed: {str(e)}"
                        })
                        logger.error(f"Failed to approve {loan_id}: {e}")

                elif decision == "deny":
                    try:
                        await self._deny_loan(loan_id, reason)
                        results["denied"].append({
                            "id": loan_id,
                            "reason": reason,
                            "instance_id": instance_id,
                            "requesting_library": loan.get("requesting_library_id"),
                        })
                        logger.info(f"Denied inbound loan {loan_id}: {reason}")
                    except Exception as e:
                        results["errors"].append({
                            "id": loan_id,
                            "error": f"Denial failed: {str(e)}"
                        })
                        logger.error(f"Failed to deny {loan_id}: {e}")

                else:  # skip
                    results["skipped"].append({
                        "id": loan_id,
                        "reason": reason,
                        "instance_id": instance_id,
                        "requesting_library": loan.get("requesting_library_id"),
                    })
                    logger.info(f"Skipped inbound loan {loan_id}: {reason}")

            except Exception as e:
                results["errors"].append({
                    "id": loan_id,
                    "error": str(e)
                })
                logger.error(f"Error processing inbound loan {loan_id}: {e}")

        # Log summary
        logger.info(
            f"Inbound Loan Processor completed: "
            f"{len(results['approved'])} approved, "
            f"{len(results['denied'])} denied, "
            f"{len(results['skipped'])} skipped, "
            f"{len(results['errors'])} errors"
        )

        return results

    async def process_single_loan(self, loan: dict) -> dict:
        """Process a single inbound loan request.

        Args:
            loan: The inbound loan request data

        Returns:
            Processing result for this loan
        """
        loan_id = loan.get("id", "unknown")
        instance_id = loan.get("instance_id")

        if not instance_id:
            return {
                "id": loan_id,
                "decision": "skip",
                "reason": "Missing instance_id in loan request"
            }

        try:
            availability = await self._check_availability(instance_id)
            decision, reason = evaluate_inbound_loan(loan, availability)

            result = {
                "id": loan_id,
                "decision": decision,
                "reason": reason,
                "instance_id": instance_id,
            }

            if decision == "approve":
                await self._reserve_instance(instance_id, loan_id)
                await self._approve_loan(loan_id, reason)
            elif decision == "deny":
                await self._deny_loan(loan_id, reason)

            return result

        except Exception as e:
            return {
                "id": loan_id,
                "decision": "error",
                "reason": str(e),
                "instance_id": instance_id,
            }


# Convenience function for creating agent in different contexts
def get_agent() -> LlmAgent:
    """Get the Inbound Loan Agent instance.

    This is the main entry point for ADK integration.
    """
    return create_inbound_loan_agent()


if __name__ == "__main__":
    # For testing the agent standalone
    import asyncio

    async def main():
        agent = create_inbound_loan_agent()
        print(f"Created Inbound Loan Agent: {agent.name}")
        print(f"Model: {agent.model}")
        print(f"Tools configured: {len(agent.tools)}")

    asyncio.run(main())
