import { Component, EventEmitter, OnInit, Output, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatIconModule } from '@angular/material/icon';

import { RunService } from '../../core/services/run.service';
import { BenchmarkConfigRequest, BenchmarkModelOption, RunCreateRequest } from '../../shared/models/benchmark.models';

@Component({
  selector: 'app-run-config-dialog',
  standalone: true,
  imports: [CommonModule, FormsModule, MatIconModule],
  template: `
    <div class="dialog-backdrop" (click)="onCancel()">
      <div class="dialog-panel" (click)="$event.stopPropagation()">
        <div class="dialog-header">
          <h2><mat-icon>tune</mat-icon> Configure Benchmark Run</h2>
          <button class="close-btn" (click)="onCancel()">
            <mat-icon>close</mat-icon>
          </button>
        </div>

        <div class="dialog-body">
          <!-- Run Mode -->
          <div class="field">
            <label>Run Mode</label>
            <div class="radio-group">
              <label class="radio-label">
                <input type="radio" name="runMode" value="eval" [(ngModel)]="runMode" />
                Eval (Live Agent)
              </label>
              <label class="radio-label">
                <input type="radio" name="runMode" value="pytest" [(ngModel)]="runMode" />
                Pytest (Test Suite)
              </label>
              <label class="radio-label">
                <input type="radio" name="runMode" value="benchmark" [(ngModel)]="runMode" />
                Benchmark (Open-Ended)
              </label>
            </div>
          </div>

          <!-- Suite (hidden for benchmark mode) -->
          @if (runMode !== 'benchmark') {
            <div class="field">
              <label for="suite">Suite</label>
              <select id="suite" [(ngModel)]="suite">
                <option value="scenarios">scenarios</option>
                <option value="smoke">smoke</option>
                <option value="full">full</option>
              </select>
            </div>
          }

          <!-- Benchmark Config (only for benchmark mode) -->
          @if (runMode === 'benchmark') {
            <div class="benchmark-config-section">
              <div class="config-section-header">
                <mat-icon>settings</mat-icon>
                <span>Benchmark Configuration</span>
              </div>

              <div class="config-row">
                <div class="field compact">
                  <label for="interactionCount">Interactions</label>
                  <input id="interactionCount" type="number" min="1" max="2000"
                    [(ngModel)]="bmInteractionCount" />
                </div>
                <div class="field compact">
                  <label for="timeBudget">Time Budget</label>
                  <select id="timeBudget" [(ngModel)]="bmTimeBudget">
                    <option [ngValue]="120">2 min</option>
                    <option [ngValue]="300">5 min</option>
                    <option [ngValue]="600">10 min</option>
                    <option [ngValue]="1800">30 min</option>
                    <option [ngValue]="3600">60 min</option>
                  </select>
                </div>
              </div>

              <div class="config-weights">
                <label class="weights-label">Domain Weights</label>
                <div class="config-row three-col">
                  <div class="field compact">
                    <label for="wCatalog">Catalog</label>
                    <input id="wCatalog" type="number" min="0" max="1" step="0.1"
                      [(ngModel)]="bmDomainCatalog" />
                  </div>
                  <div class="field compact">
                    <label for="wCirculation">Circulation</label>
                    <input id="wCirculation" type="number" min="0" max="1" step="0.1"
                      [(ngModel)]="bmDomainCirculation" />
                  </div>
                  <div class="field compact">
                    <label for="wIll">ILL</label>
                    <input id="wIll" type="number" min="0" max="1" step="0.1"
                      [(ngModel)]="bmDomainIll" />
                  </div>
                </div>
              </div>

              <div class="config-weights">
                <label class="weights-label">Complexity Distribution</label>
                <div class="config-row three-col">
                  <div class="field compact">
                    <label for="cSimple">Simple</label>
                    <input id="cSimple" type="number" min="0" max="1" step="0.1"
                      [(ngModel)]="bmComplexSimple" />
                  </div>
                  <div class="field compact">
                    <label for="cMedium">Medium</label>
                    <input id="cMedium" type="number" min="0" max="1" step="0.1"
                      [(ngModel)]="bmComplexMedium" />
                  </div>
                  <div class="field compact">
                    <label for="cComplex">Complex</label>
                    <input id="cComplex" type="number" min="0" max="1" step="0.1"
                      [(ngModel)]="bmComplexComplex" />
                  </div>
                </div>
              </div>

              <div class="config-row">
                <div class="toggle-row">
                  <label>
                    <input type="checkbox" [(ngModel)]="bmStatefulSequences" />
                    Stateful sequences
                  </label>
                </div>
                <div class="field compact">
                  <label for="randomSeed">Random Seed</label>
                  <input id="randomSeed" type="number" [(ngModel)]="bmRandomSeed" />
                </div>
              </div>
            </div>
          }

          <div class="field">
            <label for="model">Model Variant</label>
            <select id="model" [(ngModel)]="modelName" [disabled]="loadingModels">
              @for (model of modelOptions; track model.model_name) {
                <option [value]="model.model_name">{{ model.model_name }}</option>
              }
            </select>
            @if (modelLoadError) {
              <p class="field-hint">{{ modelLoadError }}</p>
            }
          </div>

          <!-- Chaos Profile -->
          <div class="field">
            <label for="chaos">Chaos Profile</label>
            <select id="chaos" [(ngModel)]="chaosProfile">
              <option value="">None</option>
              <option value="a2a_timeout_on_send">a2a_timeout_on_send</option>
              <option value="catalog_500_on_search">catalog_500_on_search</option>
              <option value="registry_intermittent">registry_intermittent</option>
              <option value="malformed_a2a_response">malformed_a2a_response</option>
            </select>
          </div>

          <!-- Toggles -->
          <div class="toggle-row">
            <label>
              <input type="checkbox" [(ngModel)]="includeAdk" />
              Include ADK agent tests
            </label>
          </div>

          <div class="toggle-row">
            <label>
              <input type="checkbox" [(ngModel)]="disableForensic" />
              Disable forensic assertions
            </label>
          </div>
        </div>

        <div class="dialog-footer">
          <button class="cancel-btn" (click)="onCancel()">Cancel</button>
          <button class="start-btn" (click)="onStart()">
            <mat-icon>play_arrow</mat-icon>
            Start Run
          </button>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .dialog-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.4);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 1000;
    }

    .dialog-panel {
      background: var(--bg-page, #faf9f7);
      border: 1px solid var(--stone-300, #d1cdc7);
      border-radius: 8px;
      width: 400px;
      max-width: 90vw;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
    }

    .dialog-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 16px 20px;
      border-bottom: 1px solid var(--stone-200, #e5e2dc);

      h2 {
        display: flex;
        align-items: center;
        gap: 8px;
        margin: 0;
        font-family: var(--font-serif, Georgia, serif);
        font-size: 1rem;
        font-weight: 700;
        color: var(--stone-800, #3d3832);

        mat-icon {
          font-size: 20px;
          width: 20px;
          height: 20px;
          color: var(--stone-500, #78716c);
        }
      }
    }

    .close-btn {
      background: none;
      border: none;
      cursor: pointer;
      color: var(--stone-400, #a8a29e);
      padding: 4px;
      border-radius: 4px;
      display: flex;
      align-items: center;

      &:hover { color: var(--stone-700, #44403c); }

      mat-icon { font-size: 18px; width: 18px; height: 18px; }
    }

    .dialog-body {
      padding: 20px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .field {
      display: flex;
      flex-direction: column;
      gap: 4px;

      label {
        font-family: var(--font-serif, Georgia, serif);
        font-size: 0.75rem;
        font-weight: 600;
        color: var(--stone-600, #57534e);
        text-transform: uppercase;
        letter-spacing: 0.06em;
      }

      select {
        padding: 8px 12px;
        border: 1px solid var(--stone-300, #d1cdc7);
        border-radius: 4px;
        background: white;
        font-family: var(--font-mono, monospace);
        font-size: 0.82rem;
        color: var(--stone-800, #3d3832);
        cursor: pointer;

        &:focus {
          outline: none;
          border-color: var(--stone-500, #78716c);
        }
      }
    }

    .field-hint {
      margin: 2px 0 0;
      font-size: 0.72rem;
      color: var(--stone-500, #78716c);
    }

    .radio-group {
      display: flex;
      gap: 16px;
    }

    .radio-label {
      display: flex;
      align-items: center;
      gap: 6px;
      font-family: var(--font-serif, Georgia, serif);
      font-size: 0.82rem;
      color: var(--stone-700, #44403c);
      cursor: pointer;

      input[type="radio"] {
        accent-color: var(--stone-800, #3d3832);
        width: 16px;
        height: 16px;
        cursor: pointer;
      }
    }

    .toggle-row {
      label {
        display: flex;
        align-items: center;
        gap: 8px;
        font-family: var(--font-serif, Georgia, serif);
        font-size: 0.82rem;
        color: var(--stone-700, #44403c);
        cursor: pointer;
      }

      input[type="checkbox"] {
        accent-color: var(--stone-800, #3d3832);
        width: 16px;
        height: 16px;
        cursor: pointer;
      }
    }

    .dialog-footer {
      display: flex;
      justify-content: flex-end;
      gap: 10px;
      padding: 16px 20px;
      border-top: 1px solid var(--stone-200, #e5e2dc);
    }

    .cancel-btn {
      padding: 8px 16px;
      background: var(--stone-100, #f5f5f0);
      border: 1px solid var(--stone-300, #d1cdc7);
      border-radius: 4px;
      font-family: var(--font-serif, Georgia, serif);
      font-size: 0.82rem;
      color: var(--stone-600, #57534e);
      cursor: pointer;

      &:hover { background: var(--stone-200, #e5e2dc); }
    }

    .start-btn {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 8px 18px;
      background: var(--stone-800, #3d3832);
      color: var(--bg-page, #faf9f7);
      border: 1px solid var(--stone-900, #1c1917);
      border-radius: 4px;
      font-family: var(--font-serif, Georgia, serif);
      font-size: 0.82rem;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.15s ease;

      mat-icon { font-size: 16px; width: 16px; height: 16px; }
      &:hover { background: var(--stone-700, #44403c); }
    }

    /* Benchmark Config Section */
    .benchmark-config-section {
      border: 1px solid var(--stone-200, #e5e2dc);
      border-radius: 6px;
      padding: 14px;
      background: var(--stone-50, #fafaf9);
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .config-section-header {
      display: flex;
      align-items: center;
      gap: 6px;
      font-family: var(--font-serif, Georgia, serif);
      font-size: 0.72rem;
      font-weight: 700;
      color: var(--stone-500, #78716c);
      text-transform: uppercase;
      letter-spacing: 0.06em;

      mat-icon {
        font-size: 14px;
        width: 14px;
        height: 14px;
        color: var(--stone-400, #a8a29e);
      }
    }

    .config-row {
      display: flex;
      gap: 12px;
      align-items: flex-end;
    }

    .config-row.three-col {
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
    }

    .config-weights {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .weights-label {
      font-family: var(--font-serif, Georgia, serif);
      font-size: 0.68rem;
      font-weight: 600;
      color: var(--stone-500, #78716c);
    }

    .field.compact {
      flex: 1;

      input[type="number"] {
        width: 100%;
        padding: 6px 8px;
        border: 1px solid var(--stone-300, #d1cdc7);
        border-radius: 4px;
        background: white;
        font-family: var(--font-mono, monospace);
        font-size: 0.78rem;
        color: var(--stone-800, #3d3832);

        &:focus {
          outline: none;
          border-color: var(--stone-500, #78716c);
        }
      }

      select {
        width: 100%;
      }
    }
  `]
})
export class RunConfigDialogComponent implements OnInit {
  private readonly runService = inject(RunService);

  @Output() confirm = new EventEmitter<RunCreateRequest>();
  @Output() cancel = new EventEmitter<void>();

  runMode: 'eval' | 'pytest' | 'benchmark' = 'eval';
  suite = 'scenarios';
  includeAdk = true;
  disableForensic = false;
  chaosProfile = '';
  modelOptions: BenchmarkModelOption[] = [];
  modelName = '';
  loadingModels = false;
  modelLoadError: string | null = null;

  // Benchmark config
  bmInteractionCount = 50;
  bmTimeBudget = 600;
  bmDomainCatalog = 0.3;
  bmDomainCirculation = 0.5;
  bmDomainIll = 0.2;
  bmComplexSimple = 0.5;
  bmComplexMedium = 0.3;
  bmComplexComplex = 0.2;
  bmStatefulSequences = true;
  bmRandomSeed = 42;

  ngOnInit(): void {
    this.loadModels();
  }

  private loadModels(): void {
    this.loadingModels = true;
    this.modelLoadError = null;
    this.runService.getModels().subscribe({
      next: (catalog) => {
        this.modelOptions = catalog.models;
        this.modelName = catalog.default_model;
        this.loadingModels = false;
      },
      error: () => {
        this.modelOptions = [
          { model_name: 'gemini-3-flash-preview', model_family: 'gemini', is_default: true },
          { model_name: 'gemini-3-pro-preview', model_family: 'gemini', is_default: false },
        ];
        this.modelName = this.modelOptions[0].model_name;
        this.modelLoadError = 'Model catalog unavailable. Using fallback options.';
        this.loadingModels = false;
      },
    });
  }

  onStart(): void {
    const request: RunCreateRequest = {
      suite: this.runMode === 'benchmark' ? 'benchmark' : this.suite,
      run_mode: this.runMode,
      include_adk: this.includeAdk,
      model_name: this.modelName || undefined,
    };
    if (this.disableForensic) {
      request.no_forensic = true;
    }
    if (this.chaosProfile) {
      request.chaos_profile = this.chaosProfile;
    }
    if (this.runMode === 'benchmark') {
      request.benchmark_config = {
        interaction_count: this.bmInteractionCount,
        time_budget_seconds: this.bmTimeBudget,
        domain_weights: {
          catalog: this.bmDomainCatalog,
          circulation: this.bmDomainCirculation,
          ill: this.bmDomainIll,
        },
        complexity_distribution: {
          simple: this.bmComplexSimple,
          medium: this.bmComplexMedium,
          complex: this.bmComplexComplex,
        },
        stateful_sequences: this.bmStatefulSequences,
        random_seed: this.bmRandomSeed,
      };
    }
    this.confirm.emit(request);
  }

  onCancel(): void {
    this.cancel.emit();
  }
}
