import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';

import { RunService } from '../../core/services/run.service';
import { RunConfigDialogComponent } from '../run-config-dialog/run-config-dialog.component';
import { RunCreateRequest, RunMetadata } from '../../shared/models/benchmark.models';

@Component({
  selector: 'app-run-list',
  standalone: true,
  imports: [CommonModule, MatIconModule, RunConfigDialogComponent],
  template: `
    <div class="page-container">
      <div class="page-header">
        <h1><mat-icon>science</mat-icon> Benchmark Runs</h1>
        <div class="header-actions">
          <button class="compare-btn" (click)="onCompareSelected()" [disabled]="!canCompareSelected()">
            <mat-icon>compare_arrows</mat-icon>
            Compare in Analytics
          </button>
          <button class="new-run-btn" (click)="onNewRun()" [disabled]="creating">
            <mat-icon>play_arrow</mat-icon>
            {{ creating ? 'Starting...' : 'New Benchmark Run' }}
          </button>
        </div>
      </div>

      @if (loading) {
        <div class="loading-state">
          <p>Loading runs...</p>
        </div>
      } @else if (error) {
        <div class="error-state">
          <mat-icon>error_outline</mat-icon>
          <p>{{ error }}</p>
          <button class="retry-btn" (click)="loadRuns()">Retry</button>
        </div>
      } @else if (runs.length === 0) {
        <div class="empty-state">
          <mat-icon>inbox</mat-icon>
          <p>No benchmark runs yet.</p>
          <p class="empty-hint">Click "New Benchmark Run" to start one.</p>
        </div>
      } @else {
        <div class="runs-table">
          <div class="table-header">
            <span class="col-select">Use</span>
            <span class="col-status">Status</span>
            <span class="col-id">Run ID</span>
            <span class="col-model">Model</span>
            <span class="col-suite">Suite</span>
            <span class="col-started">Started</span>
            <span class="col-duration">Duration</span>
          </div>
          @for (run of runs; track run.run_id) {
            <button class="table-row" (click)="onSelectRun(run)">
              <span class="col-select">
                <input
                  type="checkbox"
                  [checked]="isComparisonSelected(run.run_id)"
                  [disabled]="!canToggleForCompare(run)"
                  (click)="$event.stopPropagation()"
                  (change)="toggleComparisonSelection(run, $event)"
                />
              </span>
              <span class="col-status">
                <span class="status-badge" [attr.data-status]="run.status">
                  {{ run.status }}
                </span>
              </span>
              <span class="col-id mono">{{ run.run_id }}</span>
              <span class="col-model">{{ run.model_name || 'unknown' }}</span>
              <span class="col-suite">{{ run.suite }}</span>
              <span class="col-started">{{ formatTime(run.started_at) }}</span>
              <span class="col-duration">{{ formatDuration(run) }}</span>
            </button>
          }
        </div>
      }
    </div>

    @if (showConfigDialog) {
      <app-run-config-dialog
        (confirm)="onConfigConfirm($event)"
        (cancel)="onConfigCancel()"
      ></app-run-config-dialog>
    }
  `,
  styles: [`
    :host { display: block; height: 100%; overflow-y: auto; }
    .page-container { max-width: 960px; margin: 0 auto; padding: 32px 24px; }

    .page-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 24px;

      h1 {
        display: flex; align-items: center; gap: 10px;
        font-family: var(--font-serif); font-size: 1.4rem; font-weight: 700;
        color: var(--stone-800); margin: 0;

        mat-icon { font-size: 24px; width: 24px; height: 24px; color: var(--stone-500); }
      }
    }

    .header-actions {
      display: flex;
      gap: 10px;
    }

    .new-run-btn {
      display: flex; align-items: center; gap: 6px;
      padding: 8px 16px;
      background: var(--stone-800); color: var(--bg-page);
      border: 1px solid var(--stone-900); border-radius: 4px;
      font-family: var(--font-serif); font-size: 0.82rem; font-weight: 600;
      cursor: pointer; transition: background 0.15s ease;

      mat-icon { font-size: 16px; width: 16px; height: 16px; }
      &:hover { background: var(--stone-700); }
      &:disabled { opacity: 0.6; cursor: not-allowed; }
    }

    .compare-btn {
      display: flex; align-items: center; gap: 6px;
      padding: 8px 14px;
      background: white; color: var(--stone-700);
      border: 1px solid var(--stone-300); border-radius: 4px;
      font-family: var(--font-serif); font-size: 0.82rem; font-weight: 600;
      cursor: pointer;

      &:hover { background: var(--stone-50); border-color: var(--stone-400); }
      &:disabled { opacity: 0.6; cursor: not-allowed; }
      mat-icon { font-size: 16px; width: 16px; height: 16px; }
    }

    .loading-state, .empty-state, .error-state {
      text-align: center; padding: 60px 20px; color: var(--stone-400);

      mat-icon { font-size: 40px; width: 40px; height: 40px; margin-bottom: 12px; }
      p { margin: 4px 0; font-family: var(--font-serif); font-size: 0.9rem; }
    }

    .empty-hint { font-size: 0.8rem; font-style: italic; }

    .error-state { color: var(--red-800); }
    .retry-btn {
      margin-top: 12px; padding: 6px 16px;
      background: var(--stone-100); border: 1px solid var(--stone-300);
      border-radius: 4px; font-family: var(--font-serif); font-size: 0.8rem;
      cursor: pointer;
      &:hover { background: var(--stone-200); }
    }

    /* Table */
    .runs-table { border: 1px solid var(--stone-200); border-radius: 6px; overflow: hidden; }

    .table-header {
      display: flex; padding: 10px 16px; gap: 12px;
      background: var(--stone-100); border-bottom: 1px solid var(--stone-200);
      font-family: var(--font-serif); font-size: 0.65rem; font-weight: 700;
      text-transform: uppercase; letter-spacing: 0.1em; color: var(--stone-500);
    }

    .table-row {
      display: flex; padding: 12px 16px; gap: 12px; width: 100%;
      background: white; border: none; border-bottom: 1px solid var(--stone-100);
      cursor: pointer; text-align: left; font-family: var(--font-serif);
      font-size: 0.82rem; color: var(--stone-700); transition: background 0.1s ease;

      &:hover { background: var(--stone-50); }
      &:last-child { border-bottom: none; }
    }

    .col-select { width: 42px; flex-shrink: 0; text-align: center; }
    .col-status { width: 80px; flex-shrink: 0; }
    .col-id { width: 200px; flex-shrink: 0; }
    .col-model { width: 150px; flex-shrink: 0; }
    .col-suite { flex: 1; }
    .col-started { width: 150px; flex-shrink: 0; }
    .col-duration { width: 80px; flex-shrink: 0; text-align: right; }

    .mono { font-family: var(--font-mono); font-size: 0.75rem; }

    .status-badge {
      display: inline-block; padding: 2px 8px; border-radius: 3px;
      font-family: var(--font-mono); font-size: 0.65rem; font-weight: 700;
      text-transform: uppercase;

      &[data-status="passed"] { color: var(--emerald-800); background: var(--emerald-50); }
      &[data-status="failed"] { color: var(--red-800); background: var(--red-50); }
      &[data-status="running"] { color: var(--amber-700); background: var(--amber-50); }
      &[data-status="queued"] { color: var(--stone-500); background: var(--stone-100); }
    }
  `]
})
export class RunListComponent implements OnInit {
  private readonly runService = inject(RunService);
  private readonly router = inject(Router);

  runs: RunMetadata[] = [];
  loading = true;
  creating = false;
  error: string | null = null;
  showConfigDialog = false;
  selectedRunIds: string[] = [];

  ngOnInit(): void {
    this.loadRuns();
  }

  loadRuns(): void {
    this.loading = true;
    this.error = null;
    this.runService.listRuns().subscribe({
      next: (resp) => {
        this.runs = resp.runs;
        const validIds = new Set(this.runs.map((run) => run.run_id));
        this.selectedRunIds = this.selectedRunIds.filter((runId) => validIds.has(runId));
        this.loading = false;
      },
      error: () => {
        this.error = 'Failed to load runs. Is the agents service running?';
        this.loading = false;
      },
    });
  }

  onNewRun(): void {
    this.showConfigDialog = true;
  }

  onConfigConfirm(request: RunCreateRequest): void {
    this.showConfigDialog = false;
    this.creating = true;
    this.runService.createRun(request).subscribe({
      next: (resp) => {
        this.creating = false;
        this.router.navigate(['/runs', resp.run_id]);
      },
      error: () => {
        this.creating = false;
        this.error = 'Failed to create run. Is the agents service running?';
      },
    });
  }

  onConfigCancel(): void {
    this.showConfigDialog = false;
  }

  onSelectRun(run: RunMetadata): void {
    this.router.navigate(['/runs', run.run_id]);
  }

  canCompareSelected(): boolean {
    return this.selectedRunIds.length >= 2 && this.selectedRunIds.length <= 5;
  }

  isComparisonSelected(runId: string): boolean {
    return this.selectedRunIds.includes(runId);
  }

  canToggleForCompare(run: RunMetadata): boolean {
    if (this.isComparisonSelected(run.run_id)) {
      return true;
    }
    return this.isComparableRun(run) && this.selectedRunIds.length < 5;
  }

  toggleComparisonSelection(run: RunMetadata, event: Event): void {
    if (!this.isComparableRun(run)) {
      return;
    }
    const target = event.target as HTMLInputElement | null;
    const checked = !!target?.checked;
    if (checked) {
      if (!this.selectedRunIds.includes(run.run_id) && this.selectedRunIds.length < 5) {
        this.selectedRunIds = [...this.selectedRunIds, run.run_id];
      }
      return;
    }
    this.selectedRunIds = this.selectedRunIds.filter((runId) => runId !== run.run_id);
  }

  onCompareSelected(): void {
    if (!this.canCompareSelected()) return;
    this.router.navigate(['/analytics'], {
      queryParams: {
        runs: this.selectedRunIds.join(','),
      },
    });
  }

  private isComparableRun(run: RunMetadata): boolean {
    return run.status === 'passed' || run.status === 'failed';
  }

  formatTime(iso: string): string {
    try {
      const d = new Date(iso);
      return d.toLocaleString('en-US', {
        month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit',
      });
    } catch {
      return iso;
    }
  }

  formatDuration(run: RunMetadata): string {
    if (!run.completed_at) return '--';
    const start = new Date(run.started_at).getTime();
    const end = new Date(run.completed_at).getTime();
    const seconds = Math.round((end - start) / 1000);
    if (seconds < 60) return `${seconds}s`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}m ${secs}s`;
  }
}
