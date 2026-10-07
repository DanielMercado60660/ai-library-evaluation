import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';
import { FormsModule } from '@angular/forms';

import { RunService } from '../../core/services/run.service';
import {
  LeaderboardResponse,
  RunComparisonResponse,
  RunMetadata,
} from '../../shared/models/benchmark.models';

@Component({
  selector: 'app-analytics',
  standalone: true,
  imports: [CommonModule, FormsModule, MatIconModule],
  template: `
    <div class="page-container">
      <div class="page-header">
        <h1><mat-icon>analytics</mat-icon> Analytics</h1>
      </div>

      <div class="toolbar">
        <div class="suite-filter">
          <label for="suite-select">Suite</label>
          <select id="suite-select" [(ngModel)]="selectedSuite" (change)="onSuiteChanged()">
            <option value="">All suites</option>
            @for (suite of suiteOptions; track suite) {
              <option [value]="suite">{{ suite }}</option>
            }
          </select>
        </div>
        <button class="refresh-btn" (click)="refreshAll()">
          <mat-icon>refresh</mat-icon>
          Refresh
        </button>
      </div>

      <section class="panel">
        <div class="panel-header">
          <h2>Run Comparison Workbench</h2>
          <button class="compare-btn" (click)="compareSelected()" [disabled]="!canCompare() || loadingComparison">
            <mat-icon>compare_arrows</mat-icon>
            {{ loadingComparison ? 'Comparing...' : 'Compare Selected Runs' }}
          </button>
        </div>

        @if (runsLoading) {
          <p class="muted">Loading runs...</p>
        } @else if (runsError) {
          <p class="error">{{ runsError }}</p>
        } @else if (comparableRuns.length === 0) {
          <p class="muted">No completed runs available for comparison.</p>
        } @else {
          <div class="runs-table">
            <div class="runs-header">
              <span class="col-select">Use</span>
              <span class="col-run">Run</span>
              <span class="col-model">Model</span>
              <span class="col-suite">Suite</span>
              <span class="col-status">Status</span>
            </div>
            @for (run of comparableRuns; track run.run_id) {
              <label class="runs-row">
                <span class="col-select">
                  <input
                    type="checkbox"
                    [checked]="isSelected(run.run_id)"
                    [disabled]="!isSelected(run.run_id) && selectedRunIds.length >= 5"
                    (change)="toggleRun(run.run_id, $event)"
                  />
                </span>
                <span class="col-run mono">{{ run.run_id }}</span>
                <span class="col-model">{{ run.model_name || 'unknown' }}</span>
                <span class="col-suite">{{ run.suite }}</span>
                <span class="col-status">
                  <span class="status" [attr.data-status]="run.status">{{ run.status }}</span>
                </span>
              </label>
            }
          </div>
          <p class="hint">Select between 2 and 5 completed runs.</p>
        }
      </section>

      <section class="panel">
        <div class="panel-header">
          <h2>Comparison Results</h2>
        </div>

        @if (comparisonError) {
          <p class="error">{{ comparisonError }}</p>
        }

        @if (!comparison) {
          <p class="muted">Run a comparison to view side-by-side deltas.</p>
        } @else {
          <div class="result-table">
            <div class="result-header">
              <span>Run</span>
              <span>Model</span>
              <span>Completion</span>
              <span>Policy</span>
              <span>Tools</span>
              <span>Halluc.</span>
              <span>Composite</span>
            </div>
            @for (snapshot of comparison.runs; track snapshot.run_id) {
              <div class="result-row">
                <span class="mono">{{ snapshot.run_id }}</span>
                <span>{{ snapshot.model_name }}</span>
                <span>{{ snapshot.completion_rate_percent.toFixed(1) }}%</span>
                <span>{{ snapshot.policy_compliance_percent.toFixed(1) }}%</span>
                <span>{{ snapshot.tool_precision_percent.toFixed(1) }}%</span>
                <span>{{ snapshot.hallucinations }}</span>
                <span class="mono">{{ snapshot.composite_score.toFixed(2) }}</span>
              </div>
            }
          </div>

          <h3>Run Deltas</h3>
          <div class="result-table compact">
            <div class="result-header">
              <span>Run</span>
              <span>Composite Δ</span>
              <span>Completion Δ</span>
              <span>Policy Δ</span>
              <span>Tools Δ</span>
              <span>Halluc. Δ</span>
            </div>
            @for (delta of comparison.run_deltas; track delta.run_id) {
              <div class="result-row">
                <span class="mono">{{ delta.run_id }}</span>
                <span>{{ signed(delta.composite_score_delta) }}</span>
                <span>{{ signed(delta.completion_rate_delta) }}</span>
                <span>{{ signed(delta.policy_compliance_delta) }}</span>
                <span>{{ signed(delta.tool_precision_delta) }}</span>
                <span>{{ signed(delta.hallucinations_delta) }}</span>
              </div>
            }
          </div>

          <h3>Scenario Deltas</h3>
          @if (comparison.scenario_deltas.length === 0) {
            <p class="muted">No overlapping scenario IDs across selected runs.</p>
          } @else {
            <div class="result-table compact">
              <div class="result-header">
                <span>Run</span>
                <span>Scenario</span>
                <span>Completion Δ</span>
                <span>Policy Δ</span>
                <span>Tools Δ</span>
                <span>Halluc. Δ</span>
              </div>
              @for (delta of comparison.scenario_deltas; track delta.run_id + '-' + delta.scenario_id) {
                <div class="result-row">
                  <span class="mono">{{ delta.run_id }}</span>
                  <span>{{ delta.scenario_id }}</span>
                  <span>{{ signed(delta.completion_delta) }}</span>
                  <span>{{ signed(delta.policy_compliance_delta) }}</span>
                  <span>{{ signed(delta.tool_precision_delta) }}</span>
                  <span>{{ signed(delta.hallucinations_delta) }}</span>
                </div>
              }
            </div>
          }
        }
      </section>

      <section class="panel">
        <div class="panel-header">
          <h2>Leaderboard</h2>
        </div>

        @if (leaderboardError) {
          <p class="error">{{ leaderboardError }}</p>
        } @else if (!leaderboard) {
          <p class="muted">Loading leaderboard...</p>
        } @else if (leaderboard.rows.length === 0) {
          <p class="muted">No leaderboard rows available for this suite filter.</p>
        } @else {
          <div class="result-table">
            <div class="result-header">
              <span>Rank</span>
              <span>Model</span>
              <span>Runs</span>
              <span>Composite</span>
              <span>Completion</span>
              <span>Policy</span>
              <span>Tools</span>
              <span>Halluc.</span>
            </div>
            @for (row of leaderboard.rows; track row.model_name) {
              <div class="result-row">
                <span>{{ row.rank }}</span>
                <span>{{ row.model_name }}</span>
                <span>{{ row.run_count }}</span>
                <span class="mono">{{ row.avg_composite_score.toFixed(2) }}</span>
                <span>{{ row.avg_completion_rate.toFixed(1) }}%</span>
                <span>{{ row.avg_policy_compliance.toFixed(1) }}%</span>
                <span>{{ row.avg_tool_precision.toFixed(1) }}%</span>
                <span>{{ row.avg_hallucinations.toFixed(2) }}</span>
              </div>
            }
          </div>
        }
      </section>
    </div>
  `,
  styles: [`
    :host { display: block; height: 100%; overflow-y: auto; }
    .page-container { max-width: 1100px; margin: 0 auto; padding: 28px 24px; }
    .page-header { margin-bottom: 18px; }
    .page-header h1 {
      display: flex;
      align-items: center;
      gap: 8px;
      margin: 0;
      font-family: var(--font-serif);
      font-size: 1.4rem;
      color: var(--stone-800);
    }
    .toolbar {
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      margin-bottom: 16px;
      gap: 12px;
    }
    .suite-filter {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .suite-filter label {
      font-size: 0.72rem;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--stone-500);
      font-weight: 700;
    }
    .suite-filter select {
      border: 1px solid var(--stone-300);
      border-radius: 6px;
      background: white;
      padding: 8px 10px;
    }
    .refresh-btn, .compare-btn {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border: 1px solid var(--stone-300);
      background: white;
      color: var(--stone-700);
      border-radius: 6px;
      padding: 7px 12px;
      cursor: pointer;
      font-weight: 600;
    }
    .compare-btn {
      background: var(--stone-800);
      border-color: var(--stone-900);
      color: white;
    }
    .compare-btn:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }
    .panel {
      background: white;
      border: 1px solid var(--stone-200);
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 16px;
    }
    .panel-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
      gap: 12px;
    }
    .panel-header h2 {
      margin: 0;
      font-size: 0.9rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--stone-500);
    }
    .runs-table, .result-table {
      border: 1px solid var(--stone-200);
      border-radius: 6px;
      overflow: hidden;
    }
    .runs-header, .runs-row, .result-header, .result-row {
      display: grid;
      align-items: center;
      gap: 8px;
      padding: 10px 12px;
      border-bottom: 1px solid var(--stone-100);
      font-size: 0.84rem;
    }
    .runs-header, .result-header {
      background: var(--stone-100);
      font-size: 0.68rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-weight: 700;
      color: var(--stone-500);
    }
    .runs-row:last-child, .result-row:last-child { border-bottom: none; }
    .runs-header, .runs-row {
      grid-template-columns: 60px 1.8fr 1.3fr 1fr 0.8fr;
    }
    .result-header, .result-row {
      grid-template-columns: repeat(8, minmax(0, 1fr));
    }
    .result-table.compact .result-header,
    .result-table.compact .result-row {
      grid-template-columns: repeat(6, minmax(0, 1fr));
    }
    .status {
      font-size: 0.66rem;
      border-radius: 999px;
      padding: 2px 8px;
      text-transform: uppercase;
      font-weight: 700;
    }
    .status[data-status="passed"] { background: var(--emerald-50); color: var(--emerald-700); }
    .status[data-status="failed"] { background: var(--red-50); color: var(--red-700); }
    .mono { font-family: var(--font-mono); font-size: 0.75rem; }
    .hint, .muted {
      margin: 10px 0 0;
      color: var(--stone-500);
      font-size: 0.82rem;
    }
    .error {
      margin: 0;
      color: var(--red-700);
      font-size: 0.82rem;
    }
    h3 {
      margin: 14px 0 8px;
      font-size: 0.8rem;
      color: var(--stone-700);
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }
  `],
})
export class AnalyticsComponent implements OnInit {
  private readonly runService = inject(RunService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  runs: RunMetadata[] = [];
  selectedRunIds: string[] = [];
  selectedSuite = '';
  comparison: RunComparisonResponse | null = null;
  leaderboard: LeaderboardResponse | null = null;

  runsLoading = false;
  loadingComparison = false;
  runsError: string | null = null;
  comparisonError: string | null = null;
  leaderboardError: string | null = null;

  private pendingPrefillRunIds: string[] = [];

  ngOnInit(): void {
    this.route.queryParamMap.subscribe((params) => {
      const runsParam = params.get('runs');
      this.pendingPrefillRunIds = runsParam
        ? runsParam.split(',').map((id) => id.trim()).filter(Boolean)
        : [];
      this.applyPrefillRuns();
    });

    this.refreshAll();
  }

  get comparableRuns(): RunMetadata[] {
    return this.runs.filter((run) => run.status === 'passed' || run.status === 'failed');
  }

  get suiteOptions(): string[] {
    return [...new Set(this.comparableRuns.map((run) => run.suite))].sort();
  }

  refreshAll(): void {
    this.loadRuns();
    this.loadLeaderboard();
  }

  onSuiteChanged(): void {
    this.comparison = null;
    this.comparisonError = null;
    this.loadLeaderboard();
  }

  loadRuns(): void {
    this.runsLoading = true;
    this.runsError = null;
    this.runService.listRuns().subscribe({
      next: (response) => {
        this.runs = response.runs;
        this.runsLoading = false;
        this.applyPrefillRuns();
      },
      error: () => {
        this.runsLoading = false;
        this.runsError = 'Failed to load benchmark runs.';
      },
    });
  }

  loadLeaderboard(): void {
    this.leaderboardError = null;
    this.runService.getLeaderboard(this.selectedSuite || undefined, 20, 1).subscribe({
      next: (response) => {
        this.leaderboard = response;
      },
      error: () => {
        this.leaderboard = null;
        this.leaderboardError = 'Failed to load leaderboard.';
      },
    });
  }

  isSelected(runId: string): boolean {
    return this.selectedRunIds.includes(runId);
  }

  toggleRun(runId: string, event: Event): void {
    const input = event.target as HTMLInputElement | null;
    const checked = !!input?.checked;
    if (checked) {
      if (!this.selectedRunIds.includes(runId) && this.selectedRunIds.length < 5) {
        this.selectedRunIds = [...this.selectedRunIds, runId];
      }
      return;
    }
    this.selectedRunIds = this.selectedRunIds.filter((id) => id !== runId);
  }

  canCompare(): boolean {
    return this.selectedRunIds.length >= 2 && this.selectedRunIds.length <= 5;
  }

  compareSelected(): void {
    if (!this.canCompare()) return;

    this.loadingComparison = true;
    this.comparisonError = null;
    this.updateQueryRuns();
    this.runService.compareRuns({
      run_ids: this.selectedRunIds,
      suite: this.selectedSuite || undefined,
    }).subscribe({
      next: (response) => {
        this.comparison = response;
        this.loadingComparison = false;
      },
      error: () => {
        this.comparison = null;
        this.loadingComparison = false;
        this.comparisonError = 'Comparison failed. Ensure selected runs are completed and have reports.';
      },
    });
  }

  signed(value: number): string {
    const rounded = Math.round(value * 100) / 100;
    if (rounded > 0) return `+${rounded}`;
    return `${rounded}`;
  }

  private applyPrefillRuns(): void {
    if (this.pendingPrefillRunIds.length === 0 || this.comparableRuns.length === 0) {
      return;
    }
    const validRunIds = new Set(this.comparableRuns.map((run) => run.run_id));
    const selected = this.pendingPrefillRunIds
      .filter((runId) => validRunIds.has(runId))
      .slice(0, 5);
    if (selected.length > 0) {
      this.selectedRunIds = selected;
    }
  }

  private updateQueryRuns(): void {
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: {
        runs: this.selectedRunIds.join(','),
      },
      queryParamsHandling: 'merge',
      replaceUrl: true,
    });
  }
}
