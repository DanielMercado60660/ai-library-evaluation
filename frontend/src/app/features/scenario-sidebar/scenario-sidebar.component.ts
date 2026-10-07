import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';

import { AssistantRunService, AssistantRunState } from '../../core/services/assistant-run.service';
import { BenchmarkService } from '../../core/services/benchmark.service';
import { RunService } from '../../core/services/run.service';
import {
  ServiceHealthStatus,
  SystemStatusService,
} from '../../core/services/system-status.service';
import { RunConfigDialogComponent } from '../run-config-dialog/run-config-dialog.component';
import {
  RunCreateRequest,
  ScenarioManifestEntry,
  ScenarioStepDefinition,
} from '../../shared/models/benchmark.models';

@Component({
  selector: 'app-scenario-sidebar',
  standalone: true,
  imports: [CommonModule, FormsModule, MatIconModule, RunConfigDialogComponent],
  template: `
    <!-- Brand Header -->
    <div class="brand-header">
      <div class="brand-logo">
        <mat-icon>account_balance</mat-icon>
      </div>
      <div class="brand-text">
        <h1>Pachyderm</h1>
        <span class="brand-subtitle">Archive Benchmark</span>
      </div>
    </div>

    <div class="sidebar-scroll">
      <!-- Scenario List -->
      <div class="section">
        <div class="section-header-row">
          <h3 class="section-title">
            <mat-icon>description</mat-icon>
            Test Scenarios
          </h3>
          <select class="tier-filter" [(ngModel)]="selectedTier" (ngModelChange)="onTierChange()">
            <option [ngValue]="0">All Tiers</option>
            <option [ngValue]="1">T1: Catalog</option>
            <option [ngValue]="2">T2: Circulation</option>
            <option [ngValue]="3">T3: ILL / Federated</option>
          </select>
        </div>
        @if (scenarioLoading) {
          <p class="scenario-empty">Loading scenarios...</p>
        } @else if (scenarioError) {
          <p class="scenario-empty error">{{ scenarioError }}</p>
        } @else {
          <div class="scenario-list">
            @for (scenario of filteredScenarios; track scenario.id) {
              <button
                class="scenario-card"
                [class.active]="activeScenarioId === scenario.id"
                (click)="selectScenario(scenario)"
              >
                <div class="scenario-name">
                  <span>{{ getDisplayName(scenario.id) }}</span>
                  @if (activeScenarioId === scenario.id) {
                    <mat-icon class="active-icon">edit_note</mat-icon>
                  }
                </div>
                @if (activeScenarioId === scenario.id) {
                  <div class="scenario-meta">
                    {{ getDescription(scenario) }}
                  </div>
                  @if (getScenarioRunStatus(scenario.id)) {
                    <div class="scenario-run-state" [attr.data-status]="getScenarioRunStatus(scenario.id)">
                      <mat-icon class="run-icon">{{ getScenarioRunIcon(scenario.id) }}</mat-icon>
                      <span>{{ getScenarioRunStatus(scenario.id) }}</span>
                    </div>
                  }
                  @if (getScenarioSteps(scenario).length > 0) {
                    <ol class="scenario-steps">
                      @for (step of getScenarioSteps(scenario); track step.step_id) {
                        <li>
                          <span class="step-order">{{ step.order }}.</span>
                          <span class="step-title">{{ step.title }}</span>
                        </li>
                      }
                    </ol>
                  }
                }
                <div class="scenario-tier">
                  <span class="tier-badge" [attr.data-tier]="scenario.tier">
                    T{{ scenario.tier }}
                  </span>
                </div>
              </button>
            }
          </div>
        }
      </div>

      <!-- Vital Signs -->
      <div class="section">
        <h3 class="section-title">
          <mat-icon>monitor_heart</mat-icon>
          Vital Signs
        </h3>
        <div class="vitals-list">
          @for (svc of serviceHealth; track svc.id) {
            <div class="vital-row">
              <div class="vital-left">
                <span class="vital-dot" [class.ok]="svc.healthy"></span>
                <span class="vital-label">{{ svc.label }}</span>
              </div>
              <span class="vital-ping">
                {{ svc.healthy ? (svc.latencyMs ?? '?') + 'ms' : 'down' }}
              </span>
            </div>
          }
        </div>
      </div>
    </div>

    <!-- Footer -->
    <div class="sidebar-footer">
      <button class="benchmark-btn" (click)="onCommenceBenchmark()" [disabled]="benchmarkStarting">
        <mat-icon>play_arrow</mat-icon>
        {{ benchmarkStarting ? 'Starting...' : 'Commence Benchmark' }}
      </button>
      @if (benchmarkError) {
        <p class="benchmark-error">{{ benchmarkError }}</p>
      }
      @if (scenarioRunError) {
        <p class="benchmark-error">{{ scenarioRunError }}</p>
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
    :host {
      display: flex;
      flex-direction: column;
      height: 100%;
    }

    /* Brand Header */
    .brand-header {
      height: 72px;
      border-bottom: 1px solid var(--stone-200);
      display: flex;
      align-items: center;
      padding: 0 20px;
      gap: 12px;
      flex-shrink: 0;
    }

    .brand-logo {
      width: 40px;
      height: 40px;
      background: var(--stone-800);
      border-radius: 4px;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 2px 8px rgba(0,0,0,0.12);

      mat-icon {
        color: var(--bg-page);
        font-size: 22px;
        width: 22px;
        height: 22px;
      }
    }

    .brand-text {
      display: flex;
      flex-direction: column;

      h1 {
        margin: 0;
        font-family: var(--font-serif);
        font-size: 1.15rem;
        font-weight: 700;
        color: var(--stone-900);
        letter-spacing: -0.01em;
        line-height: 1.1;
      }
    }

    .brand-subtitle {
      font-size: 0.6rem;
      font-weight: 500;
      color: var(--stone-500);
      text-transform: uppercase;
      letter-spacing: 0.12em;
      margin-top: 3px;
    }

    /* Scrollable Area */
    .sidebar-scroll {
      flex: 1;
      overflow-y: auto;
      padding: 20px 0;
    }

    /* Sections */
    .section {
      padding: 0 16px;
      margin-bottom: 28px;
    }

    .section-title {
      display: flex;
      align-items: center;
      gap: 6px;
      font-family: var(--font-serif);
      font-size: 0.68rem;
      font-weight: 700;
      color: var(--stone-400);
      text-transform: uppercase;
      letter-spacing: 0.1em;
      margin: 0 0 12px 0;

      mat-icon {
        font-size: 14px;
        width: 14px;
        height: 14px;
      }
    }

    .section-header-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 12px;

      .section-title {
        margin: 0;
      }
    }

    .tier-filter {
      padding: 3px 8px;
      border: 1px solid var(--stone-300);
      border-radius: 3px;
      background: white;
      font-family: var(--font-mono);
      font-size: 0.6rem;
      color: var(--stone-600);
      cursor: pointer;

      &:focus {
        outline: none;
        border-color: var(--stone-500);
      }
    }

    /* Scenario Cards */
    .scenario-list {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .scenario-empty {
      margin: 0;
      padding: 12px 10px;
      border-radius: 4px;
      background: var(--stone-50);
      color: var(--stone-500);
      font-family: var(--font-serif);
      font-size: 0.78rem;
      line-height: 1.4;
    }

    .scenario-empty.error {
      background: var(--red-50);
      color: var(--red-800);
    }

    .scenario-card {
      width: 100%;
      text-align: left;
      padding: 10px 14px;
      border-radius: 4px;
      border: 1px solid transparent;
      background: transparent;
      color: var(--stone-500);
      cursor: pointer;
      font-family: var(--font-serif);
      font-size: 0.8rem;
      transition: all 0.15s ease;
      position: relative;

      &:hover {
        color: var(--stone-800);
        background: var(--stone-100);
      }

      &.active {
        background: white;
        border-color: var(--stone-300);
        color: var(--stone-900);
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
      }
    }

    .scenario-name {
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-weight: 600;
      font-size: 0.78rem;
      line-height: 1.3;
    }

    .active-icon {
      color: var(--emerald-700);
      font-size: 14px;
      width: 14px;
      height: 14px;
    }

    .scenario-meta {
      font-size: 0.7rem;
      color: var(--stone-500);
      margin-top: 4px;
      font-style: italic;
      line-height: 1.4;
    }

    .scenario-steps {
      margin: 8px 0 0;
      padding: 0;
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 3px;

      li {
        display: flex;
        align-items: baseline;
        gap: 4px;
        font-size: 0.66rem;
        line-height: 1.35;
        color: var(--stone-500);
      }
    }

    .step-order {
      font-family: var(--font-mono);
      color: var(--stone-400);
      min-width: 16px;
      text-align: right;
    }

    .step-title {
      font-family: var(--font-serif);
    }

    .scenario-run-state {
      margin-top: 8px;
      display: inline-flex;
      align-items: center;
      gap: 4px;
      font-family: var(--font-mono);
      font-size: 0.64rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: var(--stone-500);

      .run-icon {
        font-size: 12px;
        width: 12px;
        height: 12px;
      }

      &[data-status="starting"],
      &[data-status="queued"],
      &[data-status="running"] {
        color: var(--amber-700);
      }

      &[data-status="passed"] {
        color: var(--emerald-700);
      }

      &[data-status="failed"] {
        color: var(--red-800);
      }
    }

    .scenario-tier {
      position: absolute;
      top: 10px;
      right: -1px;
      display: none;
    }

    .tier-badge {
      font-family: var(--font-mono);
      font-size: 0.6rem;
      font-weight: 700;
      padding: 1px 5px;
      border-radius: 2px;
      color: var(--stone-500);
      background: var(--stone-100);

      &[data-tier="1"] { color: var(--emerald-700); background: var(--emerald-50); }
      &[data-tier="2"] { color: var(--amber-700); background: var(--amber-50); }
      &[data-tier="3"] { color: var(--red-800); background: var(--red-50); }
    }

    /* Vital Signs */
    .vitals-list {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .vital-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 7px 10px;
      border-radius: 4px;
      background: var(--bg-panel);
      border: 1px solid rgba(0,0,0,0.03);
    }

    .vital-left {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .vital-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: var(--amber-700);

      &.ok {
        background: var(--emerald-700);
      }
    }

    .vital-label {
      font-size: 0.75rem;
      font-weight: 500;
      color: var(--stone-600);
    }

    .vital-ping {
      font-size: 0.65rem;
      color: var(--stone-400);
      font-family: var(--font-mono);
    }

    /* Footer */
    .sidebar-footer {
      padding: 16px 16px 20px;
      border-top: 1px solid var(--stone-200);
      background: var(--bg-panel);
      flex-shrink: 0;
    }

    .benchmark-btn {
      width: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      padding: 12px 16px;
      background: var(--stone-800);
      color: var(--bg-page);
      border: 1px solid var(--stone-900);
      border-radius: 4px;
      font-family: var(--font-serif);
      font-size: 0.85rem;
      font-weight: 600;
      cursor: pointer;
      box-shadow: 0 2px 6px rgba(0,0,0,0.08);
      transition: background 0.15s ease;

      mat-icon {
        font-size: 18px;
        width: 18px;
        height: 18px;
      }

      &:hover { background: var(--stone-700); }
      &:disabled { opacity: 0.6; cursor: not-allowed; }
    }

    .benchmark-error {
      margin: 8px 0 0;
      font-family: var(--font-serif);
      font-size: 0.7rem;
      color: var(--red-800);
      text-align: center;
    }
  `],
})
export class ScenarioSidebarComponent implements OnInit {
  private readonly assistantRunService = inject(AssistantRunService);
  private readonly benchmarkService = inject(BenchmarkService);
  private readonly systemStatusService = inject(SystemStatusService);
  private readonly runService = inject(RunService);
  private readonly router = inject(Router);

  scenarios: ScenarioManifestEntry[] = [];
  filteredScenarios: ScenarioManifestEntry[] = [];
  selectedTier = 0;
  scenarioLoading = true;
  scenarioError: string | null = null;
  activeScenarioId: string | null = null;
  serviceHealth: ServiceHealthStatus[] = [];
  benchmarkStarting = false;
  benchmarkError: string | null = null;
  scenarioRunError: string | null = null;
  showConfigDialog = false;
  assistantRunState: AssistantRunState | null = null;

  ngOnInit(): void {
    this.benchmarkService.scenarios$.subscribe((scenarios) => {
      this.scenarios = scenarios;
      this.applyTierFilter();
    });

    this.benchmarkService.loadScenarios().subscribe((scenarios) => {
      this.scenarioLoading = false;
      this.scenarioError = scenarios.length === 0
        ? 'No benchmark scenarios found. Verify agents scenario manifest is available.'
        : null;
    });

    this.benchmarkService.activeScenario$.subscribe((s) => {
      this.activeScenarioId = s?.id ?? null;
    });

    this.assistantRunService.state$.subscribe((state) => {
      this.assistantRunState = state;
      this.scenarioRunError = state?.errorMessage ?? null;
    });

    this.systemStatusService.checkAllServices().subscribe({
      next: (statuses) => (this.serviceHealth = statuses),
    });
  }

  selectScenario(scenario: ScenarioManifestEntry): void {
    this.benchmarkService.selectScenario(scenario);
    this.scenarioRunError = null;
    this.assistantRunService.startScenarioRun(
      scenario,
      this.benchmarkService.getScenarioScript(scenario.id),
    );
  }

  getDisplayName(id: string): string {
    return this.benchmarkService.getScenarioDisplayName(id);
  }

  getDescription(entry: ScenarioManifestEntry): string {
    return this.benchmarkService.getScenarioDescription(entry);
  }

  getScenarioSteps(entry: ScenarioManifestEntry): ScenarioStepDefinition[] {
    return [...(entry.steps ?? [])].sort((a, b) => a.order - b.order);
  }

  getScenarioRunStatus(scenarioId: string): string | null {
    if (!this.assistantRunState) return null;
    if (this.assistantRunState.scenarioId !== scenarioId) return null;
    return this.assistantRunState.status;
  }

  getScenarioRunIcon(scenarioId: string): string {
    const status = this.getScenarioRunStatus(scenarioId);
    if (status === 'passed') return 'check_circle';
    if (status === 'failed') return 'error';
    if (status === 'running' || status === 'queued' || status === 'starting') return 'hourglass_top';
    return 'info';
  }

  onTierChange(): void {
    this.applyTierFilter();
  }

  private applyTierFilter(): void {
    if (this.selectedTier === 0) {
      this.filteredScenarios = this.scenarios;
    } else {
      this.filteredScenarios = this.scenarios.filter((s) => s.tier === this.selectedTier);
    }
  }

  onCommenceBenchmark(): void {
    this.showConfigDialog = true;
  }

  onConfigConfirm(request: RunCreateRequest): void {
    this.showConfigDialog = false;
    this.benchmarkStarting = true;
    this.benchmarkError = null;
    this.runService.createRun(request).subscribe({
      next: (resp) => {
        this.benchmarkStarting = false;
        this.router.navigate(['/runs', resp.run_id]);
      },
      error: () => {
        this.benchmarkStarting = false;
        this.benchmarkError = 'Failed to start benchmark. Is the agents service running?';
      },
    });
  }

  onConfigCancel(): void {
    this.showConfigDialog = false;
  }
}
