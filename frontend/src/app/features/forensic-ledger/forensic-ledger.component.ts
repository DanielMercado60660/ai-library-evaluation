import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';

import { AssistantRunService, AssistantRunState } from '../../core/services/assistant-run.service';
import { BenchmarkService } from '../../core/services/benchmark.service';
import {
  BenchmarkDetails,
  BenchmarkInteractionDetail,
  BenchmarkReport,
  EvalScenarioDetail,
  EvalStepDetail,
  TraceEvent,
  TraceItem,
} from '../../shared/models/benchmark.models';
import { mapTraceEventsToAuditEntries } from '../../shared/utils/audit-trace.mapper';
import { exportReportPdf } from '../../shared/utils/pdf-export';

@Component({
  selector: 'app-forensic-ledger',
  standalone: true,
  imports: [CommonModule, MatIconModule, RouterLink],
  template: `
    <!-- Header -->
    <div class="ledger-header">
      <div class="header-left">
        <mat-icon>shield</mat-icon>
        <h2>Forensic Ledger</h2>
      </div>
      <span class="live-badge" [class.active]="hasActiveData">
        {{ liveBadgeLabel }}
      </span>
    </div>

    <!-- Trace Stream -->
    <div class="trace-scroll">
      <div class="stream-header">
        <span class="stream-label">Audit Stream</span>
        @if (activeRunId) {
          <span class="stream-id">
            {{ activeRunId }}
          </span>
        } @else if (report) {
          <span class="stream-id">
            {{ report.trace_summary?.run_id }}
          </span>
        }
        @if (activeRunId) {
          <a class="open-run-link" [routerLink]="['/runs', activeRunId]">Open Run Detail</a>
        }
      </div>

      @if (isBenchmarkRun && benchmarkInteractions.length > 0) {
        <!-- Benchmark Interaction Cards -->
        @for (ix of benchmarkInteractions; track ix.interaction_id) {
          <div class="bm-card" [attr.data-status]="bmCardStatus(ix)">
            <div class="bm-card-header" (click)="toggleBmInteraction(ix.interaction_id)">
              <div class="bm-card-left">
                <mat-icon class="bm-card-icon">
                  {{ bmCardIcon(ix) }}
                </mat-icon>
                <span class="bm-card-type">{{ ix.interaction_type }}</span>
                <span class="bm-card-patron">{{ ix.patron_id }}</span>
                @if (ix.is_edge_case) {
                  <span class="bm-edge-badge">EDGE</span>
                }
              </div>
              <div class="bm-card-right">
                <span class="bm-card-domain">{{ ix.expected_domain }}</span>
                <span class="bm-card-duration">{{ formatMs(ix.duration_ms) }}</span>
                <mat-icon class="eval-expand-icon">
                  {{ expandedBmInteractions.has(ix.interaction_id) ? 'expand_less' : 'expand_more' }}
                </mat-icon>
              </div>
            </div>

            @if (expandedBmInteractions.has(ix.interaction_id)) {
              <div class="eval-step-body">
                <div class="eval-section">
                  <span class="eval-section-label">Message Sent</span>
                  <div class="eval-message patron">{{ ix.message_sent }}</div>
                </div>
                <div class="eval-section">
                  <span class="eval-section-label">Agent Response</span>
                  <div class="eval-message agent">{{ truncate(ix.agent_response, 500) || '(no response)' }}</div>
                </div>
                @if (ix.tool_calls_observed.length > 0) {
                  <div class="eval-section">
                    <span class="eval-section-label">Tool Calls</span>
                    <div class="eval-tool-chips">
                      @for (tool of ix.tool_calls_observed; track tool) {
                        <span class="eval-tool-chip">{{ tool }}</span>
                      }
                    </div>
                  </div>
                }
                <div class="eval-section">
                  <span class="eval-section-label">Validation</span>
                  <div class="bm-validation-row">
                    <span class="bm-validation-chip" [attr.data-ok]="ix.tool_engaged">
                      {{ ix.tool_engaged ? 'Tool Engaged' : 'No Tool' }}
                    </span>
                    <span class="bm-validation-chip" [attr.data-ok]="ix.coherence_score >= 0.5">
                      Coherence: {{ ix.coherence_score.toFixed(2) }}
                    </span>
                    @if (ix.hallucination_detected) {
                      <span class="bm-validation-chip" data-ok="false">Hallucination</span>
                    }
                    @if (ix.appropriate_refusal) {
                      <span class="bm-validation-chip" data-ok="true">Appropriate Refusal</span>
                    }
                  </div>
                </div>
                @if (ix.error) {
                  <div class="eval-section">
                    <span class="eval-section-label eval-error-label">Error</span>
                    <div class="eval-error-text">{{ ix.error }}</div>
                  </div>
                }
              </div>
            }
          </div>
        }
      } @else if (isEvalRun && evalSteps.length > 0) {
        <!-- Eval Step Cards -->
        @for (step of evalSteps; track step.step_id) {
          <div class="eval-step-card" [attr.data-passed]="step.passed">
            <div class="eval-step-header" (click)="toggleStep(step.step_id)">
              <div class="eval-step-header-left">
                <mat-icon class="eval-step-icon">
                  {{ step.passed ? 'check_circle' : 'cancel' }}
                </mat-icon>
                <span class="eval-step-number">Step {{ step.order }}</span>
                <span class="eval-step-id">{{ step.step_id }}</span>
              </div>
              <div class="eval-step-header-right">
                <span class="eval-step-duration">{{ formatMs(step.duration_ms) }}</span>
                <mat-icon class="eval-expand-icon">
                  {{ expandedSteps.has(step.step_id) ? 'expand_less' : 'expand_more' }}
                </mat-icon>
              </div>
            </div>

            @if (expandedSteps.has(step.step_id)) {
              <div class="eval-step-body">
                <!-- Patron Message -->
                <div class="eval-section">
                  <span class="eval-section-label">Patron Message</span>
                  <div class="eval-message patron">{{ step.patron_message }}</div>
                </div>

                <!-- Agent Response -->
                <div class="eval-section">
                  <span class="eval-section-label">Agent Response</span>
                  <div class="eval-message agent">{{ step.agent_response || '(no response)' }}</div>
                </div>

                <!-- Tool Calls -->
                @if (step.tool_calls_observed.length > 0) {
                  <div class="eval-section">
                    <span class="eval-section-label">Tool Calls</span>
                    <div class="eval-tool-chips">
                      @for (tool of step.tool_calls_observed; track tool) {
                        <span class="eval-tool-chip">{{ tool }}</span>
                      }
                    </div>
                  </div>
                }

                <!-- Assertions -->
                @if (step.assertions.length > 0) {
                  <div class="eval-section">
                    <span class="eval-section-label">Assertions</span>
                    <div class="eval-assertions">
                      @for (a of step.assertions; track $index) {
                        <div class="eval-assertion-row" [attr.data-passed]="a.passed">
                          <mat-icon class="eval-assertion-icon">
                            {{ a.passed ? 'check' : 'close' }}
                          </mat-icon>
                          <span class="eval-assertion-type">{{ a.type }}</span>
                          <span class="eval-assertion-detail">{{ a.details }}</span>
                        </div>
                      }
                    </div>
                  </div>
                }

                <!-- Error -->
                @if (step.error) {
                  <div class="eval-section">
                    <span class="eval-section-label eval-error-label">Error</span>
                    <div class="eval-error-text">{{ step.error }}</div>
                  </div>
                }
              </div>
            }
          </div>
        }
      } @else if (traceItems.length > 0) {
        @for (item of traceItems; track $index) {
          <div class="trace-item" [attr.data-status]="item.status">
            <div class="trace-top">
              <div class="trace-label-row">
                <mat-icon class="trace-icon">{{ getIcon(item.status) }}</mat-icon>
                <span class="trace-label" [attr.data-status]="item.status">
                  {{ item.label }}
                </span>
              </div>
              @if (item.time) {
                <span class="trace-time">{{ item.time }}</span>
              }
            </div>
            <div class="trace-details">{{ item.details }}</div>
          </div>
        }
      } @else {
        <div class="trace-empty">
          <mat-icon>hourglass_empty</mat-icon>
          <p>No trace data available.</p>
          <p class="trace-hint">{{ emptyTraceHint }}</p>
        </div>
      }

      <!-- Skeleton placeholder -->
      <div class="trace-skeleton">
        <div class="skel-line short"></div>
        <div class="skel-line long"></div>
      </div>
    </div>

    <!-- Session Metrics Footer -->
    <div class="metrics-footer">
      <div class="metrics-header">
        <span class="metrics-label">Session Metrics</span>
        @if (report) {
          <button class="print-link" (click)="onPrintReport()">Print Report</button>
        }
      </div>

      <div class="metrics-grid">
        <div class="metric-card">
          <div class="metric-top">
            <span class="metric-name">Completion</span>
            <mat-icon [class]="completionOk ? 'metric-ok' : 'metric-bad'">
              {{ completionOk ? 'check_circle' : 'warning' }}
            </mat-icon>
          </div>
          <div class="metric-value">{{ completionPct }}%</div>
        </div>
        <div class="metric-card">
          <div class="metric-top">
            <span class="metric-name">Hallucinations</span>
            <mat-icon [class]="hallucinations === 0 ? 'metric-ok' : 'metric-bad'">
              {{ hallucinations === 0 ? 'shield' : 'warning' }}
            </mat-icon>
          </div>
          <div class="metric-value">{{ hallucinations }}</div>
        </div>
        <div class="metric-card">
          <div class="metric-top">
            <span class="metric-name">Tool Precision</span>
            <mat-icon [class]="toolPrecisionOk ? 'metric-ok' : 'metric-bad'">
              {{ toolPrecisionOk ? 'check_circle' : 'warning' }}
            </mat-icon>
          </div>
          <div class="metric-value">{{ toolPrecisionPct }}%</div>
        </div>
        <div class="metric-card">
          <div class="metric-top">
            <span class="metric-name">Policy</span>
            <mat-icon [class]="policyOk ? 'metric-ok' : 'metric-bad'">
              {{ policyOk ? 'check_circle' : 'warning' }}
            </mat-icon>
          </div>
          <div class="metric-value">{{ policyPct }}%</div>
        </div>
      </div>

      <!-- Progress Bar -->
      <div class="progress-section">
        <div class="progress-labels">
          <span>{{ isBenchmarkRun ? 'Interactions Completed' : 'Scenarios Passed' }}</span>
          <span>{{ passed }}/{{ total }}</span>
        </div>
        <div class="progress-track">
          <div class="progress-fill" [style.width.%]="progressPct"></div>
        </div>
      </div>

      <!-- Benchmark-specific footer metrics -->
      @if (isBenchmarkRun && bmDetails) {
        <div class="bm-footer-metrics">
          <div class="bm-footer-row">
            <span class="bm-footer-label">Avg Response</span>
            <span class="bm-footer-value">{{ formatMs(bmDetails.avg_response_time_ms) }}</span>
          </div>
          <div class="bm-footer-row">
            <span class="bm-footer-label">Tool Engagement</span>
            <span class="bm-footer-value">{{ (bmDetails.tool_engagement_rate * 100).toFixed(0) }}%</span>
          </div>
          <div class="bm-footer-row">
            <span class="bm-footer-label">Error Rate</span>
            <span class="bm-footer-value" [class.metric-bad]="bmDetails.error_rate > 0.1">
              {{ (bmDetails.error_rate * 100).toFixed(1) }}%
            </span>
          </div>
          <div class="bm-footer-row">
            <span class="bm-footer-label">Wall Clock</span>
            <span class="bm-footer-value">{{ formatSeconds(bmDetails.wall_clock_seconds) }}</span>
          </div>
        </div>
      }
    </div>
  `,
  styles: [`
    :host {
      display: flex;
      flex-direction: column;
      height: 100%;
    }

    /* Header */
    .ledger-header {
      height: 72px;
      border-bottom: 1px solid var(--stone-200);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 20px;
      flex-shrink: 0;

      .header-left {
        display: flex;
        align-items: center;
        gap: 8px;

        mat-icon {
          font-size: 18px;
          width: 18px;
          height: 18px;
          color: var(--stone-400);
        }

        h2 {
          margin: 0;
          font-family: var(--font-serif);
          font-size: 0.72rem;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.1em;
          color: var(--stone-500);
        }
      }
    }

    .live-badge {
      font-family: var(--font-serif);
      font-size: 0.6rem;
      font-weight: 700;
      padding: 3px 8px;
      border-radius: 4px;
      background: var(--stone-100);
      border: 1px solid var(--stone-200);
      color: var(--stone-500);

      &.active {
        background: white;
        color: var(--emerald-800);
        border-color: var(--stone-200);
      }
    }

    /* Trace Stream */
    .trace-scroll {
      flex: 1;
      overflow-y: auto;
      background: var(--bg-page);
    }

    .stream-header {
      position: sticky;
      top: 0;
      z-index: 2;
      background: rgba(253, 252, 248, 0.95);
      backdrop-filter: blur(6px);
      padding: 10px 16px;
      border-bottom: 1px solid var(--stone-100);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .stream-label {
      font-family: var(--font-serif);
      font-size: 0.62rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      color: var(--stone-400);
    }

    .stream-id {
      font-family: var(--font-mono);
      font-size: 0.6rem;
      color: var(--stone-500);
      background: var(--stone-100);
      padding: 2px 6px;
      border-radius: 3px;
      border: 1px solid var(--stone-200);
    }

    .open-run-link {
      margin-left: auto;
      font-size: 0.62rem;
      font-weight: 700;
      letter-spacing: 0.02em;
      color: var(--indigo-700);
      text-decoration: none;
      border: 1px solid var(--indigo-200);
      border-radius: 3px;
      padding: 2px 6px;
      background: var(--indigo-50);

      &:hover {
        background: var(--indigo-100);
      }
    }

    /* Trace Items */
    .trace-item {
      padding: 10px 16px;
      border-bottom: 1px solid var(--stone-100);
      border-left: 4px solid var(--stone-200);
      transition: background 0.1s ease;

      &:hover { background: var(--stone-50); }

      &[data-status="pass"] {
        border-left-color: var(--emerald-700);
        background: rgba(236, 253, 245, 0.2);
      }
      &[data-status="success"] {
        border-left-color: var(--emerald-700);
        background: rgba(236, 253, 245, 0.2);
      }
      &[data-status="danger"] {
        border-left-color: var(--red-800);
        background: rgba(254, 242, 242, 0.2);
      }
      &[data-status="warning"] {
        border-left-color: var(--amber-700);
        background: rgba(255, 251, 235, 0.2);
      }
    }

    .trace-top {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 4px;
    }

    .trace-label-row {
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .trace-icon {
      font-size: 14px;
      width: 14px;
      height: 14px;
    }

    .trace-label {
      font-family: var(--font-serif);
      font-size: 0.72rem;
      font-weight: 700;
      color: var(--stone-700);

      &[data-status="pass"], &[data-status="success"] { color: var(--emerald-900); }
      &[data-status="danger"] { color: var(--red-900); }
    }

    .trace-time {
      font-family: var(--font-mono);
      font-size: 0.6rem;
      color: var(--stone-400);
    }

    .trace-details {
      padding-left: 20px;
      font-family: var(--font-serif);
      font-size: 0.72rem;
      color: var(--stone-600);
      line-height: 1.5;
    }

    .trace-empty {
      text-align: center;
      padding: 40px 20px;
      color: var(--stone-400);

      mat-icon {
        font-size: 32px;
        width: 32px;
        height: 32px;
        margin-bottom: 8px;
      }

      p {
        margin: 4px 0;
        font-family: var(--font-serif);
        font-size: 0.82rem;
      }

      .trace-hint {
        font-size: 0.72rem;
        font-style: italic;
      }
    }

    /* Eval Step Cards */
    .eval-step-card {
      border-bottom: 1px solid var(--stone-100);
      border-left: 4px solid var(--stone-300);

      &[data-passed="true"] {
        border-left-color: var(--emerald-700);
      }
      &[data-passed="false"] {
        border-left-color: var(--red-800);
      }
    }

    .eval-step-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 10px 16px;
      cursor: pointer;
      transition: background 0.1s ease;

      &:hover { background: var(--stone-50); }
    }

    .eval-step-header-left {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .eval-step-icon {
      font-size: 16px;
      width: 16px;
      height: 16px;
    }

    .eval-step-card[data-passed="true"] .eval-step-icon { color: var(--emerald-700); }
    .eval-step-card[data-passed="false"] .eval-step-icon { color: var(--red-800); }

    .eval-step-number {
      font-family: var(--font-mono);
      font-size: 0.68rem;
      font-weight: 700;
      color: var(--stone-500);
    }

    .eval-step-id {
      font-family: var(--font-serif);
      font-size: 0.72rem;
      font-weight: 600;
      color: var(--stone-700);
    }

    .eval-step-header-right {
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .eval-step-duration {
      font-family: var(--font-mono);
      font-size: 0.6rem;
      color: var(--stone-400);
    }

    .eval-expand-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
      color: var(--stone-400);
    }

    .eval-step-body {
      padding: 0 16px 14px 36px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .eval-section {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .eval-section-label {
      font-family: var(--font-serif);
      font-size: 0.6rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--stone-400);
    }

    .eval-message {
      font-family: var(--font-serif);
      font-size: 0.72rem;
      line-height: 1.5;
      color: var(--stone-700);
      padding: 8px 10px;
      border-radius: 4px;
      white-space: pre-wrap;
      word-break: break-word;
      max-height: 200px;
      overflow-y: auto;

      &.patron {
        background: var(--stone-50);
        border: 1px solid var(--stone-200);
      }

      &.agent {
        background: rgba(236, 253, 245, 0.3);
        border: 1px solid rgba(16, 185, 129, 0.15);
      }
    }

    .eval-tool-chips {
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
    }

    .eval-tool-chip {
      font-family: var(--font-mono);
      font-size: 0.6rem;
      padding: 2px 8px;
      border-radius: 3px;
      background: var(--stone-100);
      border: 1px solid var(--stone-200);
      color: var(--stone-600);
    }

    .eval-assertions {
      display: flex;
      flex-direction: column;
      gap: 3px;
    }

    .eval-assertion-row {
      display: flex;
      align-items: flex-start;
      gap: 6px;
      padding: 4px 8px;
      border-radius: 3px;
      background: var(--stone-50);

      &[data-passed="true"] {
        background: rgba(236, 253, 245, 0.3);
      }
      &[data-passed="false"] {
        background: rgba(254, 242, 242, 0.3);
      }
    }

    .eval-assertion-icon {
      font-size: 14px;
      width: 14px;
      height: 14px;
      flex-shrink: 0;
      margin-top: 1px;
    }

    .eval-assertion-row[data-passed="true"] .eval-assertion-icon { color: var(--emerald-700); }
    .eval-assertion-row[data-passed="false"] .eval-assertion-icon { color: var(--red-800); }

    .eval-assertion-type {
      font-family: var(--font-mono);
      font-size: 0.6rem;
      font-weight: 700;
      color: var(--stone-500);
      flex-shrink: 0;
    }

    .eval-assertion-detail {
      font-family: var(--font-serif);
      font-size: 0.68rem;
      color: var(--stone-600);
      line-height: 1.4;
    }

    .eval-error-label {
      color: var(--red-800);
    }

    .eval-error-text {
      font-family: var(--font-mono);
      font-size: 0.68rem;
      color: var(--red-800);
      padding: 6px 10px;
      border-radius: 4px;
      background: rgba(254, 242, 242, 0.3);
      border: 1px solid rgba(220, 38, 38, 0.15);
    }

    /* Benchmark Interaction Cards */
    .bm-card {
      border-bottom: 1px solid var(--stone-100);
      border-left: 4px solid var(--stone-300);

      &[data-status="pass"] { border-left-color: var(--emerald-700); }
      &[data-status="warn"] { border-left-color: var(--amber-700); }
      &[data-status="fail"] { border-left-color: var(--red-800); }
    }

    .bm-card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 8px 16px;
      cursor: pointer;
      transition: background 0.1s ease;

      &:hover { background: var(--stone-50); }
    }

    .bm-card-left {
      display: flex;
      align-items: center;
      gap: 6px;
      min-width: 0;
    }

    .bm-card-icon {
      font-size: 14px;
      width: 14px;
      height: 14px;
      flex-shrink: 0;
    }

    .bm-card[data-status="pass"] .bm-card-icon { color: var(--emerald-700); }
    .bm-card[data-status="warn"] .bm-card-icon { color: var(--amber-700); }
    .bm-card[data-status="fail"] .bm-card-icon { color: var(--red-800); }

    .bm-card-type {
      font-family: var(--font-mono);
      font-size: 0.62rem;
      font-weight: 700;
      color: var(--stone-600);
      white-space: nowrap;
    }

    .bm-card-patron {
      font-family: var(--font-mono);
      font-size: 0.58rem;
      color: var(--stone-400);
      white-space: nowrap;
    }

    .bm-edge-badge {
      font-family: var(--font-mono);
      font-size: 0.52rem;
      font-weight: 700;
      padding: 1px 4px;
      border-radius: 2px;
      background: var(--amber-100);
      color: var(--amber-800);
      border: 1px solid var(--amber-300);
    }

    .bm-card-right {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-shrink: 0;
    }

    .bm-card-domain {
      font-family: var(--font-serif);
      font-size: 0.58rem;
      font-weight: 600;
      color: var(--stone-400);
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }

    .bm-card-duration {
      font-family: var(--font-mono);
      font-size: 0.58rem;
      color: var(--stone-400);
    }

    .bm-validation-row {
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
    }

    .bm-validation-chip {
      font-family: var(--font-mono);
      font-size: 0.58rem;
      padding: 2px 6px;
      border-radius: 3px;
      border: 1px solid var(--stone-200);
      background: var(--stone-50);
      color: var(--stone-600);

      &[data-ok="true"] {
        background: rgba(236, 253, 245, 0.4);
        border-color: rgba(16, 185, 129, 0.2);
        color: var(--emerald-800);
      }

      &[data-ok="false"] {
        background: rgba(254, 242, 242, 0.4);
        border-color: rgba(220, 38, 38, 0.15);
        color: var(--red-800);
      }
    }

    /* Benchmark Footer Metrics */
    .bm-footer-metrics {
      margin-top: 12px;
      display: flex;
      flex-direction: column;
      gap: 4px;
      padding-top: 10px;
      border-top: 1px solid var(--stone-200);
    }

    .bm-footer-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .bm-footer-label {
      font-family: var(--font-serif);
      font-size: 0.62rem;
      color: var(--stone-500);
    }

    .bm-footer-value {
      font-family: var(--font-mono);
      font-size: 0.68rem;
      font-weight: 600;
      color: var(--stone-700);
    }

    /* Skeleton */
    .trace-skeleton {
      padding: 14px 16px;
      border-left: 4px solid var(--stone-200);
      background: rgba(250, 250, 249, 0.5);
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .skel-line {
      height: 8px;
      border-radius: 4px;
      animation: pulse 1.5s ease infinite;

      &.short { width: 40%; background: var(--stone-200); }
      &.long  { width: 60%; background: var(--stone-100); }
    }

    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.4; }
    }

    /* Metrics Footer */
    .metrics-footer {
      border-top: 1px solid var(--stone-200);
      background: var(--bg-panel);
      padding: 16px 20px 20px;
      flex-shrink: 0;
    }

    .metrics-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
    }

    .metrics-label {
      font-family: var(--font-serif);
      font-size: 0.62rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      color: var(--stone-400);
    }

    .print-link {
      background: none;
      border: none;
      font-family: var(--font-serif);
      font-size: 0.62rem;
      font-weight: 700;
      color: var(--stone-600);
      cursor: pointer;
      padding: 0;

      &:hover { text-decoration: underline; }
    }

    .metrics-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
    }

    .metric-card {
      background: white;
      border-radius: 4px;
      padding: 10px 12px;
      border: 1px solid var(--stone-200);
    }

    .metric-top {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 4px;

      .metric-name {
        font-family: var(--font-serif);
        font-size: 0.62rem;
        font-weight: 500;
        color: var(--stone-500);
      }

      mat-icon {
        font-size: 14px;
        width: 14px;
        height: 14px;
      }

      .metric-ok { color: var(--emerald-700); }
      .metric-bad { color: var(--red-800); }
    }

    .metric-value {
      font-family: var(--font-serif);
      font-size: 1.5rem;
      font-weight: 700;
      color: var(--stone-800);
    }

    /* Progress */
    .progress-section {
      margin-top: 14px;
    }

    .progress-labels {
      display: flex;
      justify-content: space-between;
      margin-bottom: 6px;

      span {
        font-family: var(--font-serif);
        font-size: 0.62rem;
        font-weight: 500;
        color: var(--stone-500);
      }
    }

    .progress-track {
      height: 6px;
      width: 100%;
      background: var(--stone-200);
      border-radius: 3px;
      overflow: hidden;
    }

    .progress-fill {
      height: 100%;
      background: var(--stone-600);
      border-radius: 3px;
      transition: width 0.4s ease;
    }
  `],
})
export class ForensicLedgerComponent implements OnInit {
  private readonly assistantRunService = inject(AssistantRunService);
  private readonly benchmarkService = inject(BenchmarkService);

  report: BenchmarkReport | null = null;
  traceItems: TraceItem[] = [];
  activeScenarioId: string | null = null;
  assistantRunState: AssistantRunState | null = null;
  liveTraceEvents: TraceEvent[] = [];

  // Eval step-detail view
  isEvalRun = false;
  evalSteps: EvalStepDetail[] = [];
  expandedSteps = new Set<string>();

  // Benchmark interaction view
  isBenchmarkRun = false;
  benchmarkInteractions: BenchmarkInteractionDetail[] = [];
  expandedBmInteractions = new Set<string>();
  bmDetails: BenchmarkDetails | null = null;

  // Metrics
  completionPct = 0;
  completionOk = true;
  hallucinations = 0;
  toolPrecisionPct = 0;
  toolPrecisionOk = true;
  policyPct = 0;
  policyOk = true;
  passed = 0;
  total = 0;
  progressPct = 0;

  ngOnInit(): void {
    // Load report
    this.benchmarkService.loadReport().subscribe((report) => {
      this.report = report;
      this.updateMetrics();
      this.updateTrace();
    });

    // React to scenario selection changes
    this.benchmarkService.activeScenario$.subscribe((scenario) => {
      this.activeScenarioId = scenario?.id ?? null;
      this.updateTrace();
    });

    this.assistantRunService.state$.subscribe((state) => {
      this.assistantRunState = state;
      this.updateTrace();
    });

    this.assistantRunService.traceEvents$.subscribe((events) => {
      this.liveTraceEvents = events;
      this.updateTrace();
    });
  }

  getIcon(status: string): string {
    switch (status) {
      case 'pass':
      case 'success':
        return 'check_circle';
      case 'danger':
        return 'error';
      case 'warning':
        return 'warning';
      case 'info':
        return 'info';
      default:
        return 'article';
    }
  }

  onPrintReport(): void {
    exportReportPdf(this.report);
  }

  toggleStep(stepId: string): void {
    if (this.expandedSteps.has(stepId)) {
      this.expandedSteps.delete(stepId);
    } else {
      this.expandedSteps.add(stepId);
    }
  }

  formatMs(ms: number): string {
    if (ms < 1000) return `${Math.round(ms)}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  }

  formatSeconds(seconds: number): string {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return `${mins}m ${secs}s`;
  }

  toggleBmInteraction(id: string): void {
    if (this.expandedBmInteractions.has(id)) {
      this.expandedBmInteractions.delete(id);
    } else {
      this.expandedBmInteractions.add(id);
    }
  }

  bmCardStatus(ix: BenchmarkInteractionDetail): 'pass' | 'warn' | 'fail' {
    if (ix.status === 'error' || ix.status === 'timeout') return 'fail';
    if (ix.hallucination_detected || !ix.tool_engaged) return 'warn';
    return 'pass';
  }

  bmCardIcon(ix: BenchmarkInteractionDetail): string {
    const status = this.bmCardStatus(ix);
    if (status === 'pass') return 'check_circle';
    if (status === 'warn') return 'warning';
    return 'error';
  }

  truncate(text: string, maxLen: number): string {
    if (!text || text.length <= maxLen) return text;
    return text.substring(0, maxLen) + '...';
  }

  get activeRunId(): string | null {
    return this.assistantRunState?.runId ?? null;
  }

  get hasActiveData(): boolean {
    return !!this.activeRunId || !!this.report;
  }

  get liveBadgeLabel(): string {
    if (this.activeRunId) {
      return `LIVE · ${(this.assistantRunState?.status ?? 'queued').toUpperCase()}`;
    }
    return this.report ? 'REPORT LOADED' : 'NO DATA';
  }

  get emptyTraceHint(): string {
    if (this.activeRunId) {
      return 'Live run is active. Trace events will appear as tools and steps execute.';
    }
    return 'Load a benchmark report to view the audit stream.';
  }

  private updateMetrics(): void {
    if (!this.report) return;
    const s = this.report.summary;

    if (this.report.run_mode === 'eval') {
      // Eval reports use completion_rate (0-1) rather than completion_rate_percent
      const completionRate = (s as unknown as Record<string, number>)['completion_rate'] ?? 0;
      this.completionPct = Math.round(completionRate * 100);
      this.completionOk = completionRate >= 1.0;
      this.hallucinations = s.hallucinations ?? 0;
      this.toolPrecisionPct = Math.round(s.tool_precision_percent ?? 0);
      this.toolPrecisionOk = (s.tool_precision ?? 1) >= 0.9;
      this.policyPct = Math.round(s.policy_compliance_percent ?? 0);
      this.policyOk = (s.policy_compliance ?? 1) >= 1.0;
    } else {
      this.completionPct = Math.round(s.completion_rate_percent);
      this.completionOk = s.completion >= 1.0;
      this.hallucinations = s.hallucinations;
      this.toolPrecisionPct = Math.round(s.tool_precision_percent);
      this.toolPrecisionOk = s.tool_precision >= 0.9;
      this.policyPct = Math.round(s.policy_compliance_percent);
      this.policyOk = s.policy_compliance >= 1.0;
    }

    this.passed = s.passed;
    this.total = s.total;
    this.progressPct = s.total > 0 ? Math.round((s.passed / s.total) * 100) : 0;

    // Benchmark details
    this.bmDetails = this.report.benchmark_details ?? null;
  }

  private updateTrace(): void {
    // Detect benchmark run
    const hasBenchmarkEvents = this.liveTraceEvents.some(
      (e) => e.event_type === 'benchmark_interaction_start' || e.event_type === 'benchmark_interaction_end',
    );
    const hasBenchmarkDetails = !!this.report?.benchmark_details;
    const isReportBenchmark = this.report?.run_mode === 'benchmark';

    this.isBenchmarkRun = hasBenchmarkEvents || hasBenchmarkDetails || isReportBenchmark;

    // Load benchmark interactions from report
    if (this.isBenchmarkRun && hasBenchmarkDetails && this.report?.benchmark_details) {
      this.benchmarkInteractions = this.report.benchmark_details.interactions;
    } else {
      this.benchmarkInteractions = [];
    }

    // Detect eval run from live trace events
    const hasEvalEvents = this.liveTraceEvents.some(
      (e) => e.event_type === 'eval_step_start' || e.event_type === 'eval_step_end',
    );

    // Detect eval run from loaded report
    const hasEvalDetails = !!this.report?.eval_details && Object.keys(this.report.eval_details).length > 0;
    const isReportEval = this.report?.run_mode === 'eval';

    this.isEvalRun = !this.isBenchmarkRun && (hasEvalEvents || hasEvalDetails || isReportEval);

    // Build eval steps from report eval_details if available
    if (this.isEvalRun && hasEvalDetails && this.report?.eval_details) {
      const scenarioId = this.activeScenarioId;
      if (scenarioId && this.report.eval_details[scenarioId]) {
        this.evalSteps = this.report.eval_details[scenarioId].steps;
      } else {
        // Show all steps from all scenarios
        const allSteps: EvalStepDetail[] = [];
        for (const detail of Object.values(this.report.eval_details)) {
          allSteps.push(...detail.steps);
        }
        this.evalSteps = allSteps;
      }
    } else if (this.isEvalRun && hasEvalEvents) {
      // Build eval steps from live trace events
      this.evalSteps = this.buildEvalStepsFromTrace(this.liveTraceEvents);
    } else {
      this.evalSteps = [];
    }

    if (this.activeRunId) {
      const entries = mapTraceEventsToAuditEntries(this.liveTraceEvents).filter(
        (entry) => !this.activeScenarioId || entry.scenarioId === null || entry.scenarioId === this.activeScenarioId,
      );
      this.traceItems = entries.map((entry) => ({
        type: this.resolveTraceType(entry.label),
        label: entry.label,
        status: this.mapAuditStatus(entry.status),
        time: entry.time,
        details: entry.scenarioId ? `${entry.details} · scenario=${entry.scenarioId}` : entry.details,
      }));
      return;
    }

    this.traceItems = this.benchmarkService.buildTraceItems(this.activeScenarioId);
  }

  private buildEvalStepsFromTrace(events: TraceEvent[]): EvalStepDetail[] {
    const steps: EvalStepDetail[] = [];
    const endEvents = events.filter((e) => e.event_type === 'eval_step_end');

    for (const event of endEvents) {
      const payload = event.payload ?? {};
      const stepId = (payload['step_id'] as string) ?? '';
      const order = (payload['order'] as number) ?? steps.length + 1;
      const passed = (payload['passed'] as boolean) ?? false;
      const durationMs = (payload['duration_ms'] as number) ?? 0;
      const patronMessage = (payload['patron_message'] as string) ?? '';
      const agentResponse = (payload['agent_response'] as string) ?? '';
      const toolCalls = Array.isArray(payload['tool_calls_observed'])
        ? (payload['tool_calls_observed'] as string[])
        : [];
      const assertions = Array.isArray(payload['assertions'])
        ? (payload['assertions'] as Array<{ type: string; passed: boolean; details: string }>)
        : [];

      steps.push({
        step_id: stepId,
        order,
        patron_message: patronMessage,
        agent_response: agentResponse,
        tool_calls_observed: toolCalls,
        passed,
        duration_ms: durationMs,
        error: (payload['error'] as string) ?? null,
        assertions: assertions.map((a) => ({
          type: a.type ?? '',
          passed: a.passed ?? false,
          details: a.details ?? '',
        })),
      });
    }

    return steps.sort((a, b) => a.order - b.order);
  }

  private mapAuditStatus(status: 'info' | 'running' | 'pass' | 'fail' | 'warning'): TraceItem['status'] {
    if (status === 'pass') return 'success';
    if (status === 'fail') return 'danger';
    if (status === 'running') return 'warning';
    if (status === 'warning') return 'warning';
    return 'info';
  }

  private resolveTraceType(label: string): TraceItem['type'] {
    const normalized = label.toLowerCase();
    if (normalized.startsWith('tool')) return 'tool';
    if (normalized.includes('scenario')) return 'state';
    if (normalized.includes('policy') || normalized.includes('hallucination')) return 'assertion';
    return 'state';
  }
}
