import { Injectable, inject } from '@angular/core';
import { BehaviorSubject, Subject, Subscription } from 'rxjs';

import { RunService } from './run.service';
import { UserService } from './user.service';
import {
  RunCreateRequest,
  RunMetadata,
  RunStatus,
  ScenarioManifestEntry,
  TraceEvent,
} from '../../shared/models/benchmark.models';

export type AssistantRunStatus = RunStatus | 'starting';

export interface AssistantRunState {
  runId: string | null;
  scenarioId: string;
  status: AssistantRunStatus;
  triggerSource: string;
  errorMessage: string | null;
}

export interface AssistantScriptTrigger {
  scenarioId: string;
  script: string[];
  resetChat: boolean;
}

@Injectable({
  providedIn: 'root',
})
export class AssistantRunService {
  private readonly runService = inject(RunService);
  private readonly userService = inject(UserService);

  private readonly stateSubject = new BehaviorSubject<AssistantRunState | null>(null);
  readonly state$ = this.stateSubject.asObservable();

  private readonly traceEventsSubject = new BehaviorSubject<TraceEvent[]>([]);
  readonly traceEvents$ = this.traceEventsSubject.asObservable();

  private readonly scriptTriggerSubject = new Subject<AssistantScriptTrigger>();
  readonly scriptTriggers$ = this.scriptTriggerSubject.asObservable();

  private statusPollSub?: Subscription;
  private tracePollSub?: Subscription;

  startScenarioRun(scenario: ScenarioManifestEntry, script: string[]): void {
    this.releaseRunFocus();

    this.traceEventsSubject.next([]);
    this.stateSubject.next({
      runId: null,
      scenarioId: scenario.id,
      status: 'starting',
      triggerSource: 'assistant_card',
      errorMessage: null,
    });

    this.scriptTriggerSubject.next({
      scenarioId: scenario.id,
      script,
      resetChat: true,
    });

    const request: RunCreateRequest = {
      suite: 'scenarios',
      scenario_ids: [scenario.id],
      trigger_source: 'assistant_card',
      actor_patron_id: this.userService.currentUser().id,
    };

    this.runService.createRun(request).subscribe({
      next: (response) => {
        this.stateSubject.next({
          runId: response.run_id,
          scenarioId: scenario.id,
          status: response.status,
          triggerSource: response.trigger_source || 'assistant_card',
          errorMessage: null,
        });
        this.startStatusPolling(response.run_id, scenario.id);
        this.startTracePolling(response.run_id);
      },
      error: () => {
        this.stateSubject.next({
          runId: null,
          scenarioId: scenario.id,
          status: 'failed',
          triggerSource: 'assistant_card',
          errorMessage: 'Failed to start scenario benchmark run.',
        });
      },
    });
  }

  private startStatusPolling(runId: string, scenarioId: string): void {
    this.statusPollSub?.unsubscribe();
    this.statusPollSub = this.runService.pollRunStatus(runId, 2000).subscribe({
      next: (run) => {
        if (!this.isCurrentRun(runId)) {
          return;
        }
        this.stateSubject.next({
          runId,
          scenarioId,
          status: run.status,
          triggerSource: run.trigger_source || 'assistant_card',
          errorMessage: run.error_message,
        });

        if (!this.isRunActive(run.status)) {
          this.tracePollSub?.unsubscribe();
          this.tracePollSub = undefined;
          this.refreshFinalTrace(runId);
        }
      },
      error: () => {
        if (!this.isCurrentRun(runId)) {
          return;
        }
        this.stateSubject.next({
          runId,
          scenarioId,
          status: 'failed',
          triggerSource: 'assistant_card',
          errorMessage: 'Failed to poll scenario run status.',
        });
      },
    });
  }

  private startTracePolling(runId: string): void {
    this.tracePollSub?.unsubscribe();
    this.tracePollSub = this.runService.pollRunTrace(runId, 1500).subscribe({
      next: (events) => {
        if (!this.isCurrentRun(runId)) {
          return;
        }
        this.traceEventsSubject.next(events);
      },
      error: () => {
        if (!this.isCurrentRun(runId)) {
          return;
        }
        this.traceEventsSubject.next([]);
      },
    });
  }

  private refreshFinalTrace(runId: string): void {
    this.runService.getRunTrace(runId).subscribe({
      next: (events) => {
        if (!this.isCurrentRun(runId)) {
          return;
        }
        this.traceEventsSubject.next(events);
      },
      error: () => {
        if (!this.isCurrentRun(runId)) {
          return;
        }
        this.traceEventsSubject.next([]);
      },
    });
  }

  private releaseRunFocus(): void {
    this.statusPollSub?.unsubscribe();
    this.tracePollSub?.unsubscribe();
    this.statusPollSub = undefined;
    this.tracePollSub = undefined;
  }

  private isCurrentRun(runId: string): boolean {
    return this.stateSubject.value?.runId === runId;
  }

  private isRunActive(status: RunMetadata['status']): boolean {
    return status === 'queued' || status === 'running';
  }
}
