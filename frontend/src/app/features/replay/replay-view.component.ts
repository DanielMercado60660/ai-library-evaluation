import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';

import { RunService } from '../../core/services/run.service';
import { TraceEvent } from '../../shared/models/benchmark.models';
import { downloadText } from '../../shared/utils/download';

@Component({
  selector: 'app-replay-view',
  standalone: true,
  imports: [CommonModule, MatIconModule, RouterLink],
  template: `
    <div class="page-container">
      <a [routerLink]="['/runs', runId]" class="back-link">
        <mat-icon>arrow_back</mat-icon> Back to Run
      </a>

      @if (loading) {
        <div class="loading-state"><p>Loading trace...</p></div>
      } @else if (error) {
        <div class="error-state">
          <mat-icon>error_outline</mat-icon>
          <p>{{ error }}</p>
        </div>
      } @else {
        <div class="replay-header">
          <h1><mat-icon>replay</mat-icon> Trace Replay</h1>
          <span class="event-count">{{ events.length }} events</span>
          <button class="export-btn" (click)="onExportTrace()">
            <mat-icon>download</mat-icon> Export JSONL
          </button>
        </div>

        @if (events.length === 0) {
          <div class="empty-state">
            <mat-icon>hourglass_empty</mat-icon>
            <p>No trace events recorded for this run.</p>
          </div>
        } @else {
          <div class="timeline">
            @for (event of events; track $index) {
              <div class="timeline-event" [attr.data-category]="getCategory(event)">
                <div class="event-marker">
                  <div class="marker-dot"></div>
                  @if (!$last) {
                    <div class="marker-line"></div>
                  }
                </div>
                <div class="event-content">
                  <div class="event-top">
                    <span class="event-type" [attr.data-category]="getCategory(event)">
                      {{ event.event_type }}
                    </span>
                    <span class="event-time">{{ formatTimestamp(event.timestamp) }}</span>
                  </div>
                  <div class="event-meta">
                    @if (event.scenario_id) {
                      <span class="meta-tag">
                        <mat-icon>description</mat-icon>
                        {{ event.scenario_id }}
                      </span>
                    }
                    <span class="meta-tag">
                      <mat-icon>source</mat-icon>
                      {{ event.source }}
                    </span>
                  </div>
                  @if (hasPayload(event)) {
                    <div class="event-payload">{{ formatPayload(event.payload) }}</div>
                  }
                </div>
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

    .loading-state, .error-state, .empty-state {
      text-align: center; padding: 60px 20px; color: var(--stone-400);
      mat-icon { font-size: 40px; width: 40px; height: 40px; margin-bottom: 12px; }
      p { margin: 4px 0; font-family: var(--font-serif); font-size: 0.9rem; }
    }
    .error-state { color: var(--red-800); }

    .replay-header {
      display: flex; align-items: center; gap: 12px; margin-bottom: 24px;
      h1 {
        display: flex; align-items: center; gap: 10px;
        font-family: var(--font-serif); font-size: 1.3rem; font-weight: 700;
        color: var(--stone-800); margin: 0;
        mat-icon { font-size: 24px; width: 24px; height: 24px; color: var(--stone-500); }
      }
    }
    .event-count {
      font-family: var(--font-mono); font-size: 0.7rem; font-weight: 700;
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

    /* Timeline */
    .timeline { padding-left: 8px; }

    .timeline-event {
      display: flex; gap: 16px; min-height: 60px;
    }

    .event-marker {
      display: flex; flex-direction: column; align-items: center; width: 12px; flex-shrink: 0;
    }
    .marker-dot {
      width: 10px; height: 10px; border-radius: 50%; background: var(--stone-300);
      border: 2px solid var(--bg-page); flex-shrink: 0; margin-top: 4px;
    }
    .marker-line {
      width: 2px; flex: 1; background: var(--stone-200); margin-top: 2px;
    }

    [data-category="lifecycle"] .marker-dot { background: var(--stone-600); }
    [data-category="success"] .marker-dot { background: var(--emerald-700); }
    [data-category="failure"] .marker-dot { background: var(--red-800); }
    [data-category="tool"] .marker-dot { background: var(--amber-700); }
    [data-category="safety"] .marker-dot { background: var(--amber-700); }

    .event-content {
      flex: 1; padding-bottom: 16px; min-width: 0;
    }
    .event-top {
      display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px;
    }
    .event-type {
      font-family: var(--font-mono); font-size: 0.72rem; font-weight: 700;
      padding: 2px 8px; border-radius: 3px;
      &[data-category="lifecycle"] { color: var(--stone-600); background: var(--stone-100); }
      &[data-category="success"] { color: var(--emerald-800); background: var(--emerald-50); }
      &[data-category="failure"] { color: var(--red-800); background: var(--red-50); }
      &[data-category="tool"] { color: var(--amber-700); background: var(--amber-50); }
      &[data-category="safety"] { color: var(--amber-700); background: var(--amber-50); }
    }
    .event-time {
      font-family: var(--font-mono); font-size: 0.62rem; color: var(--stone-400);
    }

    .event-meta {
      display: flex; gap: 8px; margin-bottom: 4px; flex-wrap: wrap;
    }
    .meta-tag {
      display: inline-flex; align-items: center; gap: 3px;
      font-family: var(--font-mono); font-size: 0.62rem; color: var(--stone-500);
      mat-icon { font-size: 12px; width: 12px; height: 12px; }
    }

    .event-payload {
      font-family: var(--font-mono); font-size: 0.68rem; color: var(--stone-500);
      background: var(--stone-50); padding: 6px 10px; border-radius: 3px;
      border: 1px solid var(--stone-100); white-space: pre-wrap; word-break: break-all;
      max-height: 120px; overflow-y: auto; margin-top: 4px;
    }
  `]
})
export class ReplayViewComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly runService = inject(RunService);

  runId = '';
  events: TraceEvent[] = [];
  loading = true;
  error: string | null = null;

  ngOnInit(): void {
    this.runId = this.route.snapshot.paramMap.get('runId') ?? '';
    if (!this.runId) {
      this.error = 'No run ID provided.';
      this.loading = false;
      return;
    }
    this.runService.getRunTrace(this.runId).subscribe({
      next: (events) => {
        this.events = events;
        this.loading = false;
      },
      error: () => {
        this.error = 'Trace not available for this run.';
        this.loading = false;
      },
    });
  }

  getCategory(event: TraceEvent): string {
    const eventType = event.event_type;
    if (eventType === 'tool_call') {
      const status = String(event.payload?.['status'] ?? '').toLowerCase();
      if (status === 'fail' || status === 'failed' || status === 'error') return 'failure';
      if (status === 'pass' || status === 'passed' || status === 'success') return 'success';
      return 'tool';
    }
    if (eventType === 'scenario_step_end') {
      const status = String(event.payload?.['status'] ?? '').toLowerCase();
      if (status === 'fail' || status === 'failed' || status === 'error') return 'failure';
      if (status === 'pass' || status === 'passed') return 'success';
      return 'lifecycle';
    }
    if (eventType.includes('start') || eventType.includes('end')) return 'lifecycle';
    if (eventType.includes('pass') || eventType === 'scenario_end') return 'success';
    if (eventType.includes('fail') || eventType.includes('error')) return 'failure';
    if (eventType.includes('tool')) return 'tool';
    if (eventType.includes('safety') || eventType.includes('chaos')) return 'safety';
    return 'lifecycle';
  }

  formatTimestamp(iso: string): string {
    try {
      return new Date(iso).toLocaleTimeString('en-US', {
        hour: '2-digit', minute: '2-digit', second: '2-digit', fractionalSecondDigits: 3,
      });
    } catch {
      return iso;
    }
  }

  hasPayload(event: TraceEvent): boolean {
    return Object.keys(event.payload).length > 0;
  }

  formatPayload(payload: Record<string, unknown>): string {
    const str = JSON.stringify(payload, null, 2);
    return str.length > 500 ? str.substring(0, 500) + '...' : str;
  }

  onExportTrace(): void {
    if (this.events.length > 0) {
      const jsonl = this.events.map((e) => JSON.stringify(e)).join('\n');
      downloadText(jsonl, `trace-${this.runId}.jsonl`, 'application/x-ndjson');
    }
  }
}
