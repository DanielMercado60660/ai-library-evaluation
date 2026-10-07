import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';

import { RunService } from '../../core/services/run.service';
import { BenchmarkReport } from '../../shared/models/benchmark.models';
import { downloadJson } from '../../shared/utils/download';

@Component({
  selector: 'app-report-view',
  standalone: true,
  imports: [CommonModule, MatIconModule, RouterLink],
  template: `
    <div class="page-container">
      <a [routerLink]="['/runs', runId]" class="back-link">
        <mat-icon>arrow_back</mat-icon> Back to Run
      </a>

      @if (loading) {
        <div class="loading-state"><p>Loading report...</p></div>
      } @else if (error) {
        <div class="error-state">
          <mat-icon>error_outline</mat-icon>
          <p>{{ error }}</p>
        </div>
      } @else if (report) {
        <div class="report-header">
          <h1><mat-icon>assessment</mat-icon> Benchmark Report</h1>
          <span class="schema-badge">v{{ report.schema_version }}</span>
          <button class="export-btn" (click)="onExportReport()">
            <mat-icon>download</mat-icon> Export JSON
          </button>
        </div>

        <!-- Summary Metrics -->
        <div class="metrics-grid">
          <div class="metric-card">
            <span class="metric-label">Completion</span>
            <span class="metric-value" [class.ok]="report.summary.completion >= 1.0"
              [class.bad]="report.summary.completion < 1.0">
              {{ pct(report.summary.completion_rate_percent) }}%
            </span>
          </div>
          <div class="metric-card">
            <span class="metric-label">Hallucinations</span>
            <span class="metric-value" [class.ok]="report.summary.hallucinations === 0"
              [class.bad]="report.summary.hallucinations > 0">
              {{ report.summary.hallucinations }}
            </span>
          </div>
          <div class="metric-card">
            <span class="metric-label">Tool Precision</span>
            <span class="metric-value" [class.ok]="report.summary.tool_precision >= 0.9"
              [class.bad]="report.summary.tool_precision < 0.9">
              {{ pct(report.summary.tool_precision_percent) }}%
            </span>
          </div>
          <div class="metric-card">
            <span class="metric-label">Policy Compliance</span>
            <span class="metric-value" [class.ok]="report.summary.policy_compliance >= 1.0"
              [class.bad]="report.summary.policy_compliance < 1.0">
              {{ pct(report.summary.policy_compliance_percent) }}%
            </span>
          </div>
        </div>

        <!-- Progress Bar -->
        <div class="progress-section">
          <div class="progress-labels">
            <span>Scenarios Passed</span>
            <span>{{ report.summary.passed }}/{{ report.summary.total }}</span>
          </div>
          <div class="progress-track">
            <div class="progress-fill" [style.width.%]="passRate"></div>
          </div>
        </div>

        <!-- Scenario Results Table -->
        <div class="section">
          <h2>Scenario Results</h2>
          <div class="scenario-table">
            <div class="s-header">
              <span class="s-col-status">Status</span>
              <span class="s-col-id">Scenario</span>
              <span class="s-col-tier">Tier</span>
              <span class="s-col-metric">Completion</span>
              <span class="s-col-metric">Tools</span>
              <span class="s-col-metric">Halluc.</span>
              <span class="s-col-time">Time</span>
            </div>
            @for (s of report.scenarios; track s.scenario_id) {
              <div class="s-row">
                <span class="s-col-status">
                  <span class="result-badge" [attr.data-status]="s.status">{{ s.status }}</span>
                </span>
                <span class="s-col-id">{{ formatName(s.scenario_id) }}</span>
                <span class="s-col-tier">
                  <span class="tier-badge" [attr.data-tier]="s.tier">T{{ s.tier }}</span>
                </span>
                <span class="s-col-metric">{{ pct(s.completion * 100) }}%</span>
                <span class="s-col-metric">{{ s.tool_calls_correct }}/{{ s.tool_calls_total }}</span>
                <span class="s-col-metric">{{ s.hallucinations }}</span>
                <span class="s-col-time">{{ s.duration_seconds.toFixed(2) }}s</span>
              </div>
            }
          </div>
        </div>

        <!-- Forensic Assertions -->
        @if (report.forensic_assertions.length > 0) {
          <div class="section">
            <h2>Forensic Assertions</h2>
            @for (a of report.forensic_assertions; track a.assertion_id) {
              <div class="assertion-item" [attr.data-status]="a.status">
                <div class="assertion-header">
                  <mat-icon>{{ a.status === 'pass' ? 'check_circle' : 'error' }}</mat-icon>
                  <span class="assertion-id">{{ a.assertion_id }}</span>
                  <span class="severity-badge" [attr.data-severity]="a.severity">{{ a.severity }}</span>
                </div>
                <div class="assertion-evidence">{{ a.evidence }}</div>
              </div>
            }
          </div>
        }
      }
    </div>
  `,
  styles: [`
    :host { display: block; height: 100%; overflow-y: auto; }
    .page-container { max-width: 960px; margin: 0 auto; padding: 32px 24px; }

    .back-link {
      display: inline-flex; align-items: center; gap: 4px;
      font-family: var(--font-serif); font-size: 0.78rem; font-weight: 600;
      color: var(--stone-500); text-decoration: none; margin-bottom: 20px;
      mat-icon { font-size: 16px; width: 16px; height: 16px; }
      &:hover { color: var(--stone-800); }
    }

    .loading-state, .error-state {
      text-align: center; padding: 60px 20px; color: var(--stone-400);
      mat-icon { font-size: 40px; width: 40px; height: 40px; margin-bottom: 12px; }
      p { margin: 4px 0; font-family: var(--font-serif); font-size: 0.9rem; }
    }
    .error-state { color: var(--red-800); }

    .report-header {
      display: flex; align-items: center; gap: 12px; margin-bottom: 24px;
      h1 {
        display: flex; align-items: center; gap: 10px;
        font-family: var(--font-serif); font-size: 1.3rem; font-weight: 700;
        color: var(--stone-800); margin: 0;
        mat-icon { font-size: 24px; width: 24px; height: 24px; color: var(--stone-500); }
      }
    }
    .schema-badge {
      font-family: var(--font-mono); font-size: 0.65rem; font-weight: 700;
      padding: 2px 8px; border-radius: 3px; background: var(--stone-100);
      color: var(--stone-500); border: 1px solid var(--stone-200);
    }
    .export-btn {
      display: inline-flex; align-items: center; gap: 4px; margin-left: auto;
      padding: 6px 12px; background: var(--stone-100); border: 1px solid var(--stone-300);
      border-radius: 4px; font-family: var(--font-serif); font-size: 0.75rem;
      font-weight: 600; color: var(--stone-600); cursor: pointer;
      mat-icon { font-size: 14px; width: 14px; height: 14px; }
      &:hover { background: var(--stone-200); }
    }

    /* Metrics */
    .metrics-grid {
      display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px;
    }
    .metric-card {
      background: white; border: 1px solid var(--stone-200); border-radius: 4px; padding: 14px 16px;
    }
    .metric-label {
      display: block; font-family: var(--font-serif); font-size: 0.62rem; font-weight: 700;
      text-transform: uppercase; letter-spacing: 0.1em; color: var(--stone-400); margin-bottom: 4px;
    }
    .metric-value {
      font-family: var(--font-serif); font-size: 1.5rem; font-weight: 700; color: var(--stone-800);
      &.ok { color: var(--emerald-800); }
      &.bad { color: var(--red-800); }
    }

    /* Progress */
    .progress-section { margin-bottom: 28px; }
    .progress-labels {
      display: flex; justify-content: space-between; margin-bottom: 6px;
      span {
        font-family: var(--font-serif); font-size: 0.72rem; font-weight: 500; color: var(--stone-500);
      }
    }
    .progress-track {
      height: 8px; width: 100%; background: var(--stone-200); border-radius: 4px; overflow: hidden;
    }
    .progress-fill {
      height: 100%; background: var(--emerald-700); border-radius: 4px; transition: width 0.4s ease;
    }

    /* Sections */
    .section {
      margin-bottom: 28px;
      h2 {
        font-family: var(--font-serif); font-size: 0.68rem; font-weight: 700;
        text-transform: uppercase; letter-spacing: 0.1em; color: var(--stone-400);
        margin: 0 0 12px 0;
      }
    }

    /* Scenario Table */
    .scenario-table {
      border: 1px solid var(--stone-200); border-radius: 6px; overflow: hidden;
    }
    .s-header {
      display: flex; padding: 8px 14px; gap: 8px;
      background: var(--stone-100); border-bottom: 1px solid var(--stone-200);
      font-family: var(--font-serif); font-size: 0.6rem; font-weight: 700;
      text-transform: uppercase; letter-spacing: 0.1em; color: var(--stone-500);
    }
    .s-row {
      display: flex; padding: 10px 14px; gap: 8px;
      background: white; border-bottom: 1px solid var(--stone-100);
      font-family: var(--font-serif); font-size: 0.78rem; color: var(--stone-700);
      &:last-child { border-bottom: none; }
    }
    .s-col-status { width: 70px; flex-shrink: 0; }
    .s-col-id { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .s-col-tier { width: 40px; flex-shrink: 0; text-align: center; }
    .s-col-metric { width: 70px; flex-shrink: 0; text-align: right; font-family: var(--font-mono); font-size: 0.72rem; }
    .s-col-time { width: 60px; flex-shrink: 0; text-align: right; font-family: var(--font-mono); font-size: 0.72rem; }

    .result-badge {
      display: inline-block; padding: 1px 6px; border-radius: 3px;
      font-family: var(--font-mono); font-size: 0.6rem; font-weight: 700; text-transform: uppercase;
      &[data-status="passed"] { color: var(--emerald-800); background: var(--emerald-50); }
      &[data-status="failed"] { color: var(--red-800); background: var(--red-50); }
      &[data-status="skipped"] { color: var(--stone-500); background: var(--stone-100); }
    }
    .tier-badge {
      font-family: var(--font-mono); font-size: 0.6rem; font-weight: 700;
      padding: 1px 4px; border-radius: 2px;
      &[data-tier="1"] { color: var(--emerald-700); background: var(--emerald-50); }
      &[data-tier="2"] { color: var(--amber-700); background: var(--amber-50); }
      &[data-tier="3"] { color: var(--red-800); background: var(--red-50); }
    }

    /* Assertions */
    .assertion-item {
      padding: 12px 16px; border-left: 4px solid var(--stone-200); margin-bottom: 8px;
      background: white; border-radius: 0 4px 4px 0;
      &[data-status="pass"] { border-left-color: var(--emerald-700); }
      &[data-status="fail"] { border-left-color: var(--red-800); }
    }
    .assertion-header {
      display: flex; align-items: center; gap: 8px; margin-bottom: 4px;
      mat-icon { font-size: 16px; width: 16px; height: 16px; }
    }
    .assertion-item[data-status="pass"] .assertion-header mat-icon { color: var(--emerald-700); }
    .assertion-item[data-status="fail"] .assertion-header mat-icon { color: var(--red-800); }
    .assertion-id {
      font-family: var(--font-mono); font-size: 0.75rem; font-weight: 700; color: var(--stone-700);
    }
    .severity-badge {
      font-family: var(--font-mono); font-size: 0.55rem; font-weight: 700; text-transform: uppercase;
      padding: 1px 5px; border-radius: 2px;
      &[data-severity="critical"] { color: var(--red-800); background: var(--red-50); }
      &[data-severity="warning"] { color: var(--amber-700); background: var(--amber-50); }
      &[data-severity="info"] { color: var(--stone-500); background: var(--stone-100); }
    }
    .assertion-evidence {
      padding-left: 24px; font-family: var(--font-serif); font-size: 0.78rem;
      color: var(--stone-600); line-height: 1.5;
    }
  `]
})
export class ReportViewComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly runService = inject(RunService);

  runId = '';
  report: BenchmarkReport | null = null;
  loading = true;
  error: string | null = null;
  passRate = 0;

  ngOnInit(): void {
    this.runId = this.route.snapshot.paramMap.get('runId') ?? '';
    if (!this.runId) {
      this.error = 'No run ID provided.';
      this.loading = false;
      return;
    }
    this.runService.getRunReport(this.runId).subscribe({
      next: (report) => {
        this.report = report;
        this.passRate = report.summary.total > 0
          ? Math.round((report.summary.passed / report.summary.total) * 100) : 0;
        this.loading = false;
      },
      error: () => {
        this.error = 'Report not available for this run.';
        this.loading = false;
      },
    });
  }

  pct(value: number): number {
    return Math.round(value);
  }

  formatName(id: string): string {
    return id.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  }

  onExportReport(): void {
    if (this.report) {
      downloadJson(this.report, `benchmark-report-${this.runId}.json`);
    }
  }
}
