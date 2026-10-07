import { Component } from '@angular/core';
import { ChatComponent } from '../chat/chat.component';
import { ScenarioSidebarComponent } from '../scenario-sidebar/scenario-sidebar.component';
import { ForensicLedgerComponent } from '../forensic-ledger/forensic-ledger.component';

@Component({
  selector: 'app-chat-page',
  standalone: true,
  imports: [ChatComponent, ScenarioSidebarComponent, ForensicLedgerComponent],
  template: `
    <div class="console-shell">
      <app-scenario-sidebar class="panel-left"></app-scenario-sidebar>
      <app-chat class="panel-center"></app-chat>
      <app-forensic-ledger class="panel-right"></app-forensic-ledger>
    </div>
  `,
  styles: [`
    :host {
      display: block;
      height: 100%;
    }

    .console-shell {
      display: flex;
      height: 100%;
      background: var(--bg-page);
      overflow: hidden;
    }

    .panel-left {
      width: 280px;
      min-width: 280px;
      border-right: 1px solid var(--stone-200);
      background: var(--bg-sidebar);
      display: flex;
      flex-direction: column;
      z-index: 2;
    }

    .panel-center {
      flex: 1;
      min-width: 0;
      display: flex;
      flex-direction: column;
      position: relative;
      background: var(--bg-page);
    }

    .panel-right {
      width: 400px;
      min-width: 400px;
      border-left: 1px solid var(--stone-200);
      background: var(--bg-sidebar);
      display: flex;
      flex-direction: column;
      z-index: 1;
    }
  `]
})
export class ChatPageComponent {}
