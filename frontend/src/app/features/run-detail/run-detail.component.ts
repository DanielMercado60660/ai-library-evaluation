import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';
import { Subscription } from 'rxjs';

import { RunService } from '../../core/services/run.service';
import { RunMetadata, TraceEvent } from '../../shared/models/benchmark.models';
import { AuditStreamEntry, mapTraceEventsToAuditEntries } from '../../shared/utils/audit-trace.mapper';
import { downloadJson, downloadText } from '../../shared/utils/download';

@Component({
  selector: 'app-run-detail',
  standalone: true,
  imports: [CommonModule, MatIconModule, RouterLink],
  template: `
    <div class="page-container">
      <a routerLink="/runs" class="back-link">
        <mat-icon>arrow_back</mat-icon> All Runs
      </a>

      @if (loading) {
        <div class="loading-state"><p>Loading run...</p></div>
      } @else if (error) {
        <div class="error-state">
          <mat-icon>error_outline</mat-icon>
          <p>{{ error }}</p>
        </div>
      } @else if (run) {
        <div class="run-header">
          <div class="run-title">
            <h1><mat-icon>assignment</mat-icon> {{ run.run_id }}</h1>
            <span class="status-badge" [attr.data-status]="run.status">{{ run.status }}</span>
            @if (isRunActive(run.status)) {
              <span class="live-badge">Live Audit</span>
            }
          </div>
        </div>

        <div class="detail-grid">
          <div class="detail-card">
            <span class="detail-label">Suite</span>
            <span class="detail-value">{{ run.suite }}</span>
          </div>
          <div class="detail-card">
            <span class="detail-label">Started</span>
            <span class="detail-value">{{ formatTime(run.started_at) }}</span>
          </div>
          <div class="detail-card">
            <span class="detail-label">Completed</span>
            <span class="detail-value">{{ run.completed_at ? formatTime(run.completed_at) : 'In progress...' }}</span>
          </div>
          <div class="detail-card">
            <span class="detail-label">Duration</span>
            <span class="detail-value">{{ formatDuration(run) }}</span>
          </div>
        </div>

        @if (run.error_message) {
          <div class="error-banner">
            <mat-icon>warning</mat-icon>
            <span>{{ run.error_message }}</span>
          </div>
        }

        <div class="audit-section">
          <h2>Audit Stream</h2>
          @if (auditEntries.length === 0) {
            <div class="empty-audit">
              <mat-icon>hourglass_empty</mat-icon>
              <p>Waiting for benchmark trace events...</p>
            </div>
          } @else {
            <div class="audit-list">
              @for (entry of auditEntries; track entry.id) {
                <div class="audit-item" [attr.data-status]="entry.status">
                  <div class="audit-top">
                    <span class="audit-label">{{ entry.label }}</span>
                    <span class="audit-time">{{ entry.time }}</span>
                  </div>
                  <div class="audit-details">{{ entry.details }}</div>
                  @if (entry.scenarioId) {
                    <div class="audit-scenario">{{ entry.scenarioId }}</div>
                  }
                </div>
              }
            </div>
          }
        </div>

        <div class="actions-section">
          <h2>Actions</h2>
          <div class="action-links">
            @if (run.report_path) {
              <a [routerLink]="['/reports', run.run_id]" class="action-card">
                <mat-icon>assessment</mat-icon>
                <span>View Report</span>
              </a>
              <button class="action-card" (click)="onDownloadReport()">
                <mat-icon>download</mat-icon>
                <span>Download Report</span>
              </button>
            } @else {
              <div class="action-card disabled">
                <mat-icon>assessment</mat-icon>
                <span>Report not ready</span>
              </div>
            }
            @if (run.trace_path) {
              <a [routerLink]="['/replay', run.run_id]" class="action-card">
                <mat-icon>replay</mat-icon>
                <span>View Trace</span>
              </a>
              <button class="action-card" (click)="onDownloadTrace()">
                <mat-icon>download</mat-icon>
                <span>Download Trace</span>
              </button>
            } @else {
              <div class="action-card disabled">
                <mat-icon>replay</mat-icon>
                <span>Trace not ready</span>
              </div>
            }
            <button class="action-card" (click)="onCompareRun()">
              <mat-icon>compare_arrows</mat-icon>
              <span>Compare With Another Run</span>
            </button>
          </div>
        </div>

        @if (run.artifact_paths.length > 0) {
          <div class="artifacts-section">
            <h2>Artifacts</h2>
            <ul class="artifact-list">
              @for (path of run.artifact_paths; track path) {
                <li class="artifact-item">
                  <mat-icon>description</mat-icon>
                  {{ path }}
                </li>
              }
            </ul>
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

    .run-header { margin-bottom: 24px; }
    .run-title {
      display: flex; align-items: center; gap: 12px;
      h1 {
        display: flex; align-items: center; gap: 10px;
        font-family: var(--font-serif); font-size: 1.3rem; font-weight: 700;
        color: var(--stone-800); margin: 0;
        mat-icon { font-size: 24px; width: 24px; height: 24px; color: var(--stone-500); }
      }
    }

    .status-badge {
      display: inline-block; padding: 3px 10px; border-radius: 3px;
      font-family: var(--font-mono); font-size: 0.7rem; font-weight: 700; text-transform: uppercase;
      &[data-status="passed"] { color: var(--emerald-800); background: var(--emerald-50); }
      &[data-status="failed"] { color: var(--red-800); background: var(--red-50); }
      &[data-status="running"] { color: var(--amber-700); background: var(--amber-50); }
      &[data-status="queued"] { color: var(--stone-500); background: var(--stone-100); }
    }

    .live-badge {
      display: inline-block;
      padding: 3px 10px;
      border-radius: 3px;
      font-family: var(--font-mono);
      font-size: 0.68rem;
      font-weight: 700;
      text-transform: uppercase;
      color: var(--indigo-700);
      background: var(--indigo-50);
      border: 1px solid var(--indigo-200);
    }

    .detail-grid {
      display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 24px;
    }
    .detail-card {
      background: white; border: 1px solid var(--stone-200); border-radius: 4px; padding: 14px 16px;
    }
    .detail-label {
      display: block; font-family: var(--font-serif); font-size: 0.62rem; font-weight: 700;
      text-transform: uppercase; letter-spacing: 0.1em; color: var(--stone-400); margin-bottom: 4px;
    }
    .detail-value {
      font-family: var(--font-serif); font-size: 0.9rem; font-weight: 600; color: var(--stone-800);
    }

    .error-banner {
      display: flex; align-items: flex-start; gap: 8px;
      padding: 12px 16px; background: var(--red-50); border: 1px solid rgba(220,38,38,0.2);
      border-radius: 4px; margin-bottom: 24px;
      mat-icon { color: var(--red-800); font-size: 18px; width: 18px; height: 18px; flex-shrink: 0; }
      span { font-family: var(--font-serif); font-size: 0.82rem; color: var(--red-900); }
    }

    .audit-section {
      margin-bottom: 24px;

      h2 {
        font-family: var(--font-serif);
        font-size: 0.68rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: var(--stone-400);
        margin: 0 0 12px 0;
      }
    }

    .empty-audit {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 12px 14px;
      border: 1px dashed var(--stone-300);
      border-radius: 4px;
      color: var(--stone-500);
      background: var(--stone-50);

      mat-icon {
        font-size: 18px;
        width: 18px;
        height: 18px;
      }

      p {
        margin: 0;
        font-size: 0.8rem;
      }
    }

    .audit-list {
      border: 1px solid var(--stone-200);
      border-radius: 6px;
      overflow: hidden;
      background: white;
      max-height: 360px;
      overflow-y: auto;
    }

    .audit-item {
      padding: 10px 12px;
      border-bottom: 1px solid var(--stone-100);
      border-left: 3px solid var(--stone-300);

      &:last-child {
        border-bottom: none;
      }

      &[data-status="running"] {
        border-left-color: var(--amber-700);
      }

      &[data-status="pass"] {
        border-left-color: var(--emerald-700);
      }

      &[data-status="fail"] {
        border-left-color: var(--red-700);
      }

      &[data-status="warning"] {
        border-left-color: var(--amber-700);
      }
    }

    .audit-top {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 8px;
    }

    .audit-label {
      font-family: var(--font-serif);
      font-size: 0.78rem;
      font-weight: 700;
      color: var(--stone-800);
    }

    .audit-time {
      font-family: var(--font-mono);
      font-size: 0.64rem;
      color: var(--stone-400);
      white-space: nowrap;
    }

    .audit-details {
      margin-top: 4px;
      font-size: 0.76rem;
      color: var(--stone-600);
      line-height: 1.45;
    }

    .audit-scenario {
      margin-top: 4px;
      font-family: var(--font-mono);
      font-size: 0.66rem;
      color: var(--stone-500);
    }

    .actions-section, .artifacts-section {
      margin-bottom: 24px;
      h2 {
        font-family: var(--font-serif); font-size: 0.68rem; font-weight: 700;
        text-transform: uppercase; letter-spacing: 0.1em; color: var(--stone-400);
        margin: 0 0 12px 0;
      }
    }

    .action-links { display: flex; gap: 12px; }
    .action-card {
      display: flex; align-items: center; gap: 8px;
      padding: 12px 20px; border: 1px solid var(--stone-200); border-radius: 4px;
      background: white; text-decoration: none; color: var(--stone-700);
      font-family: var(--font-serif); font-size: 0.85rem; font-weight: 600;
      transition: all 0.15s ease; cursor: pointer;
      mat-icon { font-size: 18px; width: 18px; height: 18px; color: var(--stone-500); }
      &:hover { border-color: var(--stone-400); background: var(--stone-50); }
      &.disabled {
        opacity: 0.5; cursor: not-allowed; color: var(--stone-400);
        &:hover { border-color: var(--stone-200); background: white; }
      }
    }

    .artifact-list { list-style: none; padding: 0; margin: 0; }
    .artifact-item {
      display: flex; align-items: center; gap: 8px;
      padding: 8px 12px; border-bottom: 1px solid var(--stone-100);
      font-family: var(--font-mono); font-size: 0.75rem; color: var(--stone-600);
      mat-icon { font-size: 14px; width: 14px; height: 14px; color: var(--stone-400); }
    }
  `]
})
export class RunDetailComponent implements OnInit, OnDestroy {
  private readonly route = inject(ActivatedRoute);
  private readonly runService = inject(RunService);
  private readonly router = inject(Router);

  run: RunMetadata | null = null;
  traceEvents: TraceEvent[] = [];
  auditEntries: AuditStreamEntry[] = [];
  loading = true;
  error: string | null = null;
  private pollSub?: Subscription;
  private tracePollSub?: Subscription;

  ngOnInit(): void {
    const runId = this.route.snapshot.paramMap.get('runId');
    if (!runId) {
      this.error = 'No run ID provided.';
      this.loading = false;
      return;
    }
    this.loadRun(runId);
  }

  ngOnDestroy(): void {
    this.pollSub?.unsubscribe();
    this.tracePollSub?.unsubscribe();
  }

  private loadRun(runId: string): void {
    this.runService.getRun(runId).subscribe({
      next: (run) => {
        this.run = run;
        this.loading = false;
        this.refreshTrace(runId);
        if (this.isRunActive(run.status)) {
          this.startPolling(runId);
          this.startTracePolling(runId);
        }
      },
      error: () => {
        this.error = `Run '${runId}' not found.`;
        this.loading = false;
      },
    });
  }

  private startPolling(runId: string): void {
    this.pollSub = this.runService.pollRunStatus(runId).subscribe({
      next: (run) => {
        this.run = run;
        if (this.isRunActive(run.status)) {
          this.startTracePolling(runId);
          return;
        }
        this.tracePollSub?.unsubscribe();
        this.tracePollSub = undefined;
        this.refreshTrace(runId);
      },
    });
  }

  private startTracePolling(runId: string): void {
    if (this.tracePollSub) return;
    this.tracePollSub = this.runService.pollRunTrace(runId, 2000).subscribe({
      next: (events) => {
        this.traceEvents = events;
        this.auditEntries = mapTraceEventsToAuditEntries(events, (timestamp) => this.formatTime(timestamp));
      },
    });
  }

  private refreshTrace(runId: string): void {
    this.runService.getRunTrace(runId).subscribe({
      next: (events) => {
        this.traceEvents = events;
        this.auditEntries = mapTraceEventsToAuditEntries(events, (timestamp) => this.formatTime(timestamp));
      },
      error: () => {
        this.traceEvents = [];
        this.auditEntries = [];
      },
    });
  }

  isRunActive(status: RunMetadata['status']): boolean {
    return status === 'queued' || status === 'running';
  }

  formatTime(iso: string): string {
    try {
      return new Date(iso).toLocaleString('en-US', {
        month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit',
      });
    } catch {
      return iso;
    }
  }

  formatDuration(run: RunMetadata): string {
    if (!run.completed_at) return 'In progress...';
    const seconds = Math.round(
      (new Date(run.completed_at).getTime() - new Date(run.started_at).getTime()) / 1000,
    );
    if (seconds < 60) return `${seconds}s`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}m ${secs}s`;
  }

  onDownloadReport(): void {
    if (!this.run) return;
    this.runService.getRunReport(this.run.run_id).subscribe({
      next: (report) => downloadJson(report, `benchmark-report-${this.run!.run_id}.json`),
    });
  }

  onDownloadTrace(): void {
    if (!this.run) return;
    this.runService.getRunTrace(this.run.run_id).subscribe({
      next: (events) => {
        const jsonl = events.map((e: unknown) => JSON.stringify(e)).join('\n');
        downloadText(jsonl, `trace-${this.run!.run_id}.jsonl`, 'application/x-ndjson');
      },
    });
  }

  onCompareRun(): void {
    if (!this.run) return;
    this.router.navigate(['/analytics'], {
      queryParams: {
        runs: this.run.run_id,
      },
    });
  }
}
