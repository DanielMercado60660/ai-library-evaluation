import { TraceEvent } from '../models/benchmark.models';

export interface AuditStreamEntry {
  id: string;
  label: string;
  details: string;
  time: string;
  status: 'info' | 'running' | 'pass' | 'fail' | 'warning';
  scenarioId: string | null;
}

type TimeFormatter = (isoTimestamp: string) => string;

export function mapTraceEventsToAuditEntries(
  events: TraceEvent[],
  formatTime: TimeFormatter = formatAuditTime,
): AuditStreamEntry[] {
  return events.map((event, index) => {
    const payload = event.payload ?? {};
    const payloadStatus = payloadString(payload, 'status');
    const status = resolveAuditStatus(event.event_type, payloadStatus, payload);
    const label = resolveAuditLabel(event.event_type, payload);
    const details = resolveAuditDetails(event.event_type, payload);

    return {
      id: `${event.trace_id}-${index}`,
      label,
      details,
      time: formatTime(event.timestamp),
      status,
      scenarioId: event.scenario_id,
    };
  });
}

export function formatAuditTime(isoTimestamp: string): string {
  try {
    return new Date(isoTimestamp).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return isoTimestamp;
  }
}

function resolveAuditStatus(
  eventType: string,
  payloadStatus: string,
  payload?: Record<string, unknown>,
): AuditStreamEntry['status'] {
  const normalized = payloadStatus.toLowerCase();
  if (eventType === 'tool_call') {
    if (normalized === 'running' || normalized === 'start' || normalized === 'in_progress') return 'running';
    if (normalized === 'pass' || normalized === 'passed' || normalized === 'success') return 'pass';
    if (normalized === 'fail' || normalized === 'failed' || normalized === 'error') return 'fail';
    return 'info';
  }
  if (eventType === 'eval_step_end' || eventType === 'eval_assertion_result') {
    const passed = payload?.['passed'];
    if (passed === true) return 'pass';
    if (passed === false) return 'fail';
  }
  if (eventType === 'benchmark_interaction_end') {
    const status = payloadString(payload ?? {}, 'status');
    if (status === 'error' || status === 'timeout') return 'fail';
    const hallucination = payload?.['hallucination_detected'];
    if (hallucination === true) return 'warning';
    return 'pass';
  }
  if (normalized === 'pass' || normalized === 'passed') return 'pass';
  if (normalized === 'fail' || normalized === 'failed' || normalized === 'error') return 'fail';
  if (normalized === 'skipped') return 'warning';
  if (eventType.includes('start')) return 'running';
  if (eventType.includes('end')) return 'pass';
  return 'info';
}

function resolveAuditLabel(eventType: string, payload: Record<string, unknown>): string {
  if (eventType === 'tool_call') {
    const tool = payloadString(payload, 'tool') || 'tool';
    const phase = payloadString(payload, 'phase');
    if (phase === 'start') return `Tool Start: ${tool}`;
    if (phase === 'end') return `Tool End: ${tool}`;
    return `Tool Call: ${tool}`;
  }
  if (eventType === 'scenario_step_start' || eventType === 'scenario_step_end') {
    return payloadString(payload, 'title') || payloadString(payload, 'step_id') || eventType;
  }
  if (eventType === 'scenario_start') return 'Scenario Started';
  if (eventType === 'scenario_end') return 'Scenario Completed';
  if (eventType === 'benchmark_run_start') return 'Benchmark Run Started';
  if (eventType === 'benchmark_run_end') return 'Benchmark Run Completed';
  if (eventType === 'eval_step_start') {
    const stepId = payloadString(payload, 'step_id');
    const order = typeof payload['order'] === 'number' ? payload['order'] : 0;
    return stepId ? `Step ${order}: ${stepId}` : `Eval Step ${order}`;
  }
  if (eventType === 'eval_step_end') {
    const stepId = payloadString(payload, 'step_id');
    const passed = payload['passed'];
    const icon = passed ? 'PASS' : 'FAIL';
    return stepId ? `Step Result: ${stepId} [${icon}]` : `Eval Step Result [${icon}]`;
  }
  if (eventType === 'eval_assertion_result') {
    const assertionType = payloadString(payload, 'assertion_type') || payloadString(payload, 'type');
    const passed = payload['passed'];
    return `Assertion: ${assertionType} ${passed ? '[PASS]' : '[FAIL]'}`;
  }
  if (eventType === 'benchmark_interaction_start') {
    const interactionType = payloadString(payload, 'interaction_type') || 'interaction';
    const patronId = payloadString(payload, 'patron_id');
    return patronId ? `Benchmark: ${interactionType} (${patronId})` : `Benchmark: ${interactionType}`;
  }
  if (eventType === 'benchmark_interaction_end') {
    const interactionType = payloadString(payload, 'interaction_type') || 'interaction';
    const status = payloadString(payload, 'status') || 'completed';
    return `Benchmark Result: ${interactionType} [${status.toUpperCase()}]`;
  }
  return eventType.replace(/_/g, ' ');
}

function resolveAuditDetails(eventType: string, payload: Record<string, unknown>): string {
  if (eventType === 'tool_call') {
    const status = payloadString(payload, 'status');
    const callId = payloadString(payload, 'call_id');
    const duration = typeof payload['duration_ms'] === 'number' ? payload['duration_ms'] : null;
    const detailParts: string[] = [];
    if (status) detailParts.push(`Status: ${status}`);
    if (duration !== null) detailParts.push(`Duration: ${duration}ms`);
    if (callId) detailParts.push(`Call: ${callId}`);
    const input = payload['input'];
    const output = payload['output'];
    const error = payloadString(payload, 'error');
    if (error) {
      detailParts.push(`Error: ${error}`);
    } else if (output) {
      detailParts.push(`Output: ${JSON.stringify(output)}`);
    } else if (input) {
      detailParts.push(`Input: ${JSON.stringify(input)}`);
    }
    return detailParts.join(' · ') || 'Tool call event.';
  }
  if (eventType === 'scenario_step_start') {
    return payloadString(payload, 'description') || 'Step execution started.';
  }
  if (eventType === 'scenario_step_end') {
    const phase = payloadString(payload, 'phase');
    const status = payloadString(payload, 'status') || 'unknown';
    return phase ? `Phase: ${phase} · Outcome: ${status}` : `Outcome: ${status}`;
  }
  if (eventType === 'scenario_end') {
    const status = payloadString(payload, 'status');
    const taxonomy = payloadString(payload, 'taxonomy');
    if (status && taxonomy) return `Status: ${status} · Taxonomy: ${taxonomy}`;
    if (status) return `Status: ${status}`;
  }
  if (eventType === 'eval_step_start') {
    const message = payloadString(payload, 'patron_message');
    return message ? `Patron: "${message.substring(0, 120)}${message.length > 120 ? '...' : ''}"` : 'Eval step starting.';
  }
  if (eventType === 'eval_step_end') {
    const durationMs = typeof payload['duration_ms'] === 'number' ? payload['duration_ms'] : null;
    const toolCalls = Array.isArray(payload['tool_calls_observed']) ? payload['tool_calls_observed'] as string[] : [];
    const parts: string[] = [];
    if (durationMs !== null) parts.push(`Duration: ${Math.round(durationMs)}ms`);
    if (toolCalls.length > 0) parts.push(`Tools: ${toolCalls.join(', ')}`);
    const assertions = typeof payload['total_assertions'] === 'number' ? payload['total_assertions'] : null;
    const assertionsPassed = typeof payload['passed_assertions'] === 'number' ? payload['passed_assertions'] : null;
    if (assertions !== null && assertionsPassed !== null) parts.push(`Assertions: ${assertionsPassed}/${assertions}`);
    return parts.length > 0 ? parts.join(' · ') : 'Eval step completed.';
  }
  if (eventType === 'eval_assertion_result') {
    const details = payloadString(payload, 'details');
    return details || 'Assertion evaluated.';
  }
  if (eventType === 'benchmark_interaction_start') {
    const message = payloadString(payload, 'message');
    const domain = payloadString(payload, 'expected_domain');
    const parts: string[] = [];
    if (domain) parts.push(`Domain: ${domain}`);
    if (message) parts.push(`"${message.substring(0, 100)}${message.length > 100 ? '...' : ''}"`);
    return parts.length > 0 ? parts.join(' · ') : 'Benchmark interaction starting.';
  }
  if (eventType === 'benchmark_interaction_end') {
    const durationMs = typeof payload['duration_ms'] === 'number' ? payload['duration_ms'] : null;
    const toolEngaged = payload['tool_engaged'];
    const coherence = typeof payload['coherence_score'] === 'number' ? payload['coherence_score'] : null;
    const hallucination = payload['hallucination_detected'];
    const parts: string[] = [];
    if (durationMs !== null) parts.push(`${Math.round(durationMs)}ms`);
    if (toolEngaged !== undefined) parts.push(toolEngaged ? 'Tool engaged' : 'No tool');
    if (coherence !== null) parts.push(`Coherence: ${coherence.toFixed(2)}`);
    if (hallucination === true) parts.push('HALLUCINATION');
    return parts.length > 0 ? parts.join(' · ') : 'Benchmark interaction completed.';
  }

  const serialized = JSON.stringify(payload);
  return serialized && serialized !== '{}' ? serialized : 'No additional details.';
}

function payloadString(payload: Record<string, unknown>, key: string): string {
  const value = payload[key];
  return typeof value === 'string' ? value : '';
}
