"""ILL Approval Agent - Automated approval/denial of ILL requests using ADK + MCP.

This agent uses Google ADK (Agent Development Kit) to process pending ILL requests.
It connects to MCP servers for direct database access to:
- ILL service (approval queues, request management)
- Circulation service (patron eligibility checks)
- Catalog service (book availability)

The agent applies policy rules to make approval decisions autonomously.
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


# Policy rules for ILL approval decisions
ILL_APPROVAL_POLICY = """
## ILL Approval Policy Rules

You are an automated ILL (Inter-Library Loan) Approval Agent for the Hanno Memorial Library.
Your job is to review pending ILL requests and make approval decisions based on these rules:

### Auto-Approve Criteria (approve immediately):
1. Patron has no blocks and fines < $5.00
2. Source library has fulfillment rate >= 85%
3. Request is marked as 'urgent' or 'high' priority and has been pending > 1 day

### Auto-Deny Criteria (deny immediately):
1. Patron account is blocked
2. Patron has fines >= $10.00
3. Source library has fulfillment rate < 70%
4. Source library is not active or doesn't allow lending

### Manual Review Required (do not auto-approve/deny):
1. Patron fines between $5.00 and $10.00
2. Source library fulfillment rate between 70% and 85%
3. Request has been pending > 7 days without patron justification
4. Any edge cases not covered by above rules

### Decision Process:
1. First, get the pending outbound approval queue
2. For each request:
   a. Check patron eligibility using the circulation MCP tools
   b. Review the enriched library context already in the queue data
   c. Apply the policy rules above
   d. Make a decision: approve, deny, or skip (manual review)
   e. For approvals: call approve_ill_request with your librarian_id
   f. For denials: call deny_ill_request with a clear reason
3. Log all decisions with reasoning

### Important:
- Your librarian_id for all actions is: "ill-approval-agent"
- Always provide clear notes explaining your decision
- If unsure, skip the request for manual review
- Be consistent in applying policy rules
"""


def create_ill_approval_agent(
    ill_mcp_path: str | None = None,
    circulation_mcp_path: str | None = None,
) -> LlmAgent:
    """Create an ILL Approval Agent with MCP tool access.

    Args:
        ill_mcp_path: Path to the ILL MCP server script
        circulation_mcp_path: Path to the Circulation MCP server script

    Returns:
        Configured LlmAgent instance
    """
    tools = []

    # Default paths if not provided (for Docker deployment)
    if ill_mcp_path is None:
        ill_mcp_path = "/app/services/ill/src/ill/mcp_server.py"
    if circulation_mcp_path is None:
        circulation_mcp_path = "/app/services/circulation/src/circulation/mcp_server.py"

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
                "approve_ill_request",
                "deny_ill_request",
                "get_queue_statistics",
                "query_audit_trail",
            ]
        )
        tools.append(ill_toolset)
        logger.info("ILL MCP toolset configured")
    except Exception as e:
        logger.warning(f"Failed to configure ILL MCP toolset: {e}")

    # Add Circulation MCP toolset
    try:
        circulation_toolset = McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command="python",
                    args=["-m", "circulation.mcp_server"],
                    env={
                        "DATABASE_URL": "sqlite:///./db/circulation.db",
                        "PYTHONPATH": "/app/services/circulation/src:/app/shared/src"
                    }
                )
            ),
            tool_filter=[
                "check_patron_eligibility",
                "calculate_patron_fines",
            ]
        )
        tools.append(circulation_toolset)
        logger.info("Circulation MCP toolset configured")
    except Exception as e:
        logger.warning(f"Failed to configure Circulation MCP toolset: {e}")

    # Create the agent
    model_ref = build_model_adapter().to_adk_model_ref()
    agent = LlmAgent(
        model=model_ref,
        name="ill_approval_agent",
        description="Automated ILL request approval agent that reviews pending requests and makes approval decisions based on policy rules.",
        instruction=ILL_APPROVAL_POLICY,
        tools=tools,
    )
    # Track toolsets on agent so callers can clean up MCP connections
    agent._mcp_toolsets = tools  # type: ignore[attr-defined]

    return agent


# Standalone functions for direct tool usage without full ADK agent

async def check_patron_for_ill(patron_id: str, circulation_tools: dict) -> dict:
    """Check if a patron is eligible for ILL using circulation data.

    Args:
        patron_id: The patron ID to check
        circulation_tools: Dictionary of circulation tool functions

    Returns:
        Dictionary with eligibility status and reasons
    """
    check_eligibility = circulation_tools.get("check_patron_eligibility")
    if not check_eligibility:
        return {"eligible": False, "reason": "Circulation tools not available"}

    result = await check_eligibility(patron_id)
    return json.loads(result) if isinstance(result, str) else result


def evaluate_request_for_approval(
    request: dict,
    patron_eligibility: dict,
) -> tuple[str, str]:
    """Evaluate an ILL request against policy rules.

    Args:
        request: The ILL request data from the queue
        patron_eligibility: Patron eligibility check result

    Returns:
        Tuple of (decision, reason) where decision is 'approve', 'deny', or 'skip'
    """
    # Check for auto-deny conditions
    if not patron_eligibility.get("eligible", False):
        issues = patron_eligibility.get("issues", [])
        if any(i["type"] == "blocked" for i in issues):
            return ("deny", "Patron account is blocked")
        if any(i["type"] == "fines" for i in issues):
            return ("deny", f"Outstanding fines exceed $10.00: ${patron_eligibility.get('total_fines', 0):.2f}")

    total_fines = patron_eligibility.get("total_fines", 0)

    # Check library context
    library_context = request.get("library_context", {})
    fulfillment_rate = library_context.get("fulfillment_rate")

    if fulfillment_rate is not None and fulfillment_rate < 0.70:
        return ("deny", f"Source library has low fulfillment rate ({fulfillment_rate:.0%})")

    # Check for auto-approve conditions
    priority = request.get("priority", "normal")
    days_pending = request.get("days_pending", 0)

    # Good patron + good library = auto-approve
    if total_fines < 5.00 and (fulfillment_rate is None or fulfillment_rate >= 0.85):
        return ("approve", "Patron in good standing, reliable source library")

    # Urgent/high priority pending > 1 day
    if priority in ("urgent", "high") and days_pending > 1:
        if total_fines < 10.00 and (fulfillment_rate is None or fulfillment_rate >= 0.70):
            return ("approve", f"High priority request pending {days_pending} days, patron eligible")

    # Check for manual review conditions
    if 5.00 <= total_fines < 10.00:
        return ("skip", f"Patron fines (${total_fines:.2f}) require manual review")

    if fulfillment_rate is not None and 0.70 <= fulfillment_rate < 0.85:
        return ("skip", f"Library fulfillment rate ({fulfillment_rate:.0%}) requires manual review")

    if days_pending > 7 and not request.get("patron_justification"):
        return ("skip", "Request pending > 7 days without justification - manual review required")

    # Default to manual review for edge cases
    return ("skip", "Edge case - manual review recommended")


class ILLApprovalProcessor:
    """Processor for batch ILL approval using policy rules."""

    def __init__(self, ill_tools: dict, circulation_tools: dict):
        """Initialize the processor.

        Args:
            ill_tools: Dictionary of ILL MCP tool functions
            circulation_tools: Dictionary of Circulation MCP tool functions
        """
        self.ill_tools = ill_tools
        self.circulation_tools = circulation_tools
        self.agent_id = "ill-approval-agent"

    async def _get_pending_queue(self) -> list[dict]:
        """Fetch the pending outbound approval queue.

        Returns:
            List of pending ILL requests
        """
        get_queue = self.ill_tools.get("get_pending_outbound_queue")
        if not get_queue:
            logger.warning("get_pending_outbound_queue tool not available")
            return []

        try:
            result = await get_queue()
            if isinstance(result, str):
                result = json.loads(result)
            return result.get("items", [])
        except Exception as e:
            logger.error(f"Error fetching pending queue: {e}")
            return []

    async def _check_patron_eligibility(self, patron_id: str) -> dict:
        """Check patron eligibility for ILL.

        Args:
            patron_id: The patron ID to check

        Returns:
            Eligibility result dictionary
        """
        check_eligibility = self.circulation_tools.get("check_patron_eligibility")
        if not check_eligibility:
            return {"eligible": True, "total_fines": 0, "issues": []}

        try:
            result = await check_eligibility(patron_id)
            if isinstance(result, str):
                result = json.loads(result)
            return result
        except Exception as e:
            logger.error(f"Error checking patron eligibility: {e}")
            return {"eligible": True, "total_fines": 0, "issues": [], "error": str(e)}

    async def _approve_request(self, request_id: str, reason: str) -> dict:
        """Approve an ILL request.

        Args:
            request_id: The request ID to approve
            reason: Reason for approval

        Returns:
            Approval result
        """
        approve = self.ill_tools.get("approve_ill_request")
        if not approve:
            raise ValueError("approve_ill_request tool not available")

        return await approve(
            request_id=request_id,
            librarian_id=self.agent_id,
            notes=reason,
        )

    async def _deny_request(self, request_id: str, reason: str) -> dict:
        """Deny an ILL request.

        Args:
            request_id: The request ID to deny
            reason: Reason for denial

        Returns:
            Denial result
        """
        deny = self.ill_tools.get("deny_ill_request")
        if not deny:
            raise ValueError("deny_ill_request tool not available")

        return await deny(
            request_id=request_id,
            librarian_id=self.agent_id,
            reason=reason,
        )

    async def process_pending_queue(self) -> dict:
        """Process all pending ILL requests.

        Returns:
            Summary of processing results with structure:
            {
                "approved": [{"id": str, "reason": str}, ...],
                "denied": [{"id": str, "reason": str}, ...],
                "skipped": [{"id": str, "reason": str}, ...],
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

        logger.info("ILL Approval Processor started")
        logger.info(f"Agent ID: {self.agent_id}")

        # Fetch pending queue
        try:
            queue = await self._get_pending_queue()
            logger.info(f"Fetched {len(queue)} pending requests")
        except Exception as e:
            logger.error(f"Failed to fetch pending queue: {e}")
            results["errors"].append({"id": "queue_fetch", "error": str(e)})
            return results

        # Process each request
        for request in queue:
            request_id = request.get("id", "unknown")
            results["total_processed"] += 1

            try:
                # Get patron eligibility
                patron_id = request.get("patron_id")
                if not patron_id:
                    results["skipped"].append({
                        "id": request_id,
                        "reason": "Missing patron_id in request"
                    })
                    continue

                eligibility = await self._check_patron_eligibility(patron_id)

                # Evaluate against policy rules
                decision, reason = evaluate_request_for_approval(request, eligibility)

                # Execute decision
                if decision == "approve":
                    try:
                        await self._approve_request(request_id, reason)
                        results["approved"].append({
                            "id": request_id,
                            "reason": reason,
                            "patron_id": patron_id,
                        })
                        logger.info(f"Approved request {request_id}: {reason}")
                    except Exception as e:
                        results["errors"].append({
                            "id": request_id,
                            "error": f"Approval failed: {str(e)}"
                        })
                        logger.error(f"Failed to approve {request_id}: {e}")

                elif decision == "deny":
                    try:
                        await self._deny_request(request_id, reason)
                        results["denied"].append({
                            "id": request_id,
                            "reason": reason,
                            "patron_id": patron_id,
                        })
                        logger.info(f"Denied request {request_id}: {reason}")
                    except Exception as e:
                        results["errors"].append({
                            "id": request_id,
                            "error": f"Denial failed: {str(e)}"
                        })
                        logger.error(f"Failed to deny {request_id}: {e}")

                else:  # skip
                    results["skipped"].append({
                        "id": request_id,
                        "reason": reason,
                        "patron_id": patron_id,
                    })
                    logger.info(f"Skipped request {request_id}: {reason}")

            except Exception as e:
                results["errors"].append({
                    "id": request_id,
                    "error": str(e)
                })
                logger.error(f"Error processing request {request_id}: {e}")

        # Log summary
        logger.info(
            f"ILL Approval Processor completed: "
            f"{len(results['approved'])} approved, "
            f"{len(results['denied'])} denied, "
            f"{len(results['skipped'])} skipped, "
            f"{len(results['errors'])} errors"
        )

        return results

    async def process_single_request(self, request: dict) -> dict:
        """Process a single ILL request.

        Args:
            request: The ILL request data

        Returns:
            Processing result for this request
        """
        request_id = request.get("id", "unknown")
        patron_id = request.get("patron_id")

        if not patron_id:
            return {
                "id": request_id,
                "decision": "skip",
                "reason": "Missing patron_id in request"
            }

        try:
            eligibility = await self._check_patron_eligibility(patron_id)
            decision, reason = evaluate_request_for_approval(request, eligibility)

            result = {
                "id": request_id,
                "decision": decision,
                "reason": reason,
                "patron_id": patron_id,
            }

            if decision == "approve":
                await self._approve_request(request_id, reason)
            elif decision == "deny":
                await self._deny_request(request_id, reason)

            return result

        except Exception as e:
            return {
                "id": request_id,
                "decision": "error",
                "reason": str(e),
                "patron_id": patron_id,
            }


# Convenience function for creating agent in different contexts
def get_agent() -> LlmAgent:
    """Get the ILL Approval Agent instance.

    This is the main entry point for ADK integration.
    """
    return create_ill_approval_agent()


if __name__ == "__main__":
    # For testing the agent standalone
    import asyncio

    async def main():
        agent = create_ill_approval_agent()
        print(f"Created ILL Approval Agent: {agent.name}")
        print(f"Model: {agent.model}")
        print(f"Tools configured: {len(agent.tools)}")

    asyncio.run(main())
