"""AI Agents for the library system.

This module provides ADK-based agents using Google ADK best practices:

1. Core Agents (ADK LlmAgent):
   - FrontDeskAgent - Patron-facing chat agent with sub-agents
   - CatalogAgent - Catalog search specialist
   - CirculationAgent - Circulation operations

2. ADK + MCP Agents:
   - ILLApprovalAgent - Automated ILL request approval
   - InboundLoanAgent - Automated inbound loan processing

3. WorkflowAgents (ADK SequentialAgent):
   - ILLApprovalWorkflow - Multi-step ILL approval
   - InboundLoanWorkflow - Multi-step inbound loan processing
   - CheckoutWorkflow - Multi-step checkout process

4. Supporting Infrastructure:
   - Session management with DatabaseSessionService
   - MCP connection lifecycle management
   - Resilience utilities (retry, circuit breaker)
"""

# Core ADK-based agents
from agents.front_desk import FrontDeskAgent, chat_with_librarian, create_front_desk_agent
from agents.catalog_agent import CatalogAgent, catalog_search, create_catalog_agent
from agents.circulation_agent import CirculationAgent, circulation_action, create_circulation_agent

# ADK + MCP agents
from agents.ill_approval_agent import (
    create_ill_approval_agent,
    ILLApprovalProcessor,
    evaluate_request_for_approval,
)
from agents.inbound_loan_agent import (
    create_inbound_loan_agent,
    InboundLoanProcessor,
    evaluate_inbound_loan,
)

# Workflow agents
from agents.workflows import (
    ILLApprovalWorkflow,
    create_ill_approval_workflow,
    InboundLoanWorkflow,
    create_inbound_loan_workflow,
    CheckoutWorkflow,
    create_checkout_workflow,
)

# Session management
from agents.session import LibrarySessionService, LibrarySession
from agents.chat import ChatSession, ChatSessionManager, session_manager
from agents.benchmark_runner import BenchmarkRunner, DeterministicADKAdapter

# MCP connection management
from agents.mcp import MCPConnectionManager, MCP_SERVICE_CONFIGS

# Resilience utilities
from agents.utils import with_retry, CircuitBreaker, CircuitBreakerOpenError

__all__ = [
    # Core agents
    "FrontDeskAgent",
    "chat_with_librarian",
    "create_front_desk_agent",
    "CatalogAgent",
    "catalog_search",
    "create_catalog_agent",
    "CirculationAgent",
    "circulation_action",
    "create_circulation_agent",
    # ADK + MCP agents
    "create_ill_approval_agent",
    "ILLApprovalProcessor",
    "evaluate_request_for_approval",
    "create_inbound_loan_agent",
    "InboundLoanProcessor",
    "evaluate_inbound_loan",
    # Workflow agents
    "ILLApprovalWorkflow",
    "create_ill_approval_workflow",
    "InboundLoanWorkflow",
    "create_inbound_loan_workflow",
    "CheckoutWorkflow",
    "create_checkout_workflow",
    # Session management
    "LibrarySessionService",
    "LibrarySession",
    "ChatSession",
    "ChatSessionManager",
    "session_manager",
    # Benchmark runner
    "BenchmarkRunner",
    "DeterministicADKAdapter",
    # MCP connection management
    "MCPConnectionManager",
    "MCP_SERVICE_CONFIGS",
    # Resilience utilities
    "with_retry",
    "CircuitBreaker",
    "CircuitBreakerOpenError",
]
