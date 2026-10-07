import {
  AfterViewChecked,
  Component,
  ElementRef,
  OnDestroy,
  OnInit,
  ViewChild,
  inject,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatIconModule } from '@angular/material/icon';
import { Subscription } from 'rxjs';

import { AssistantRunService } from '../../core/services/assistant-run.service';
import { ChatService } from '../../core/services/chat.service';
import { BenchmarkService } from '../../core/services/benchmark.service';

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [CommonModule, FormsModule, MatIconModule],
  template: `
    <!-- Session Header -->
    <header class="session-header">
      <div class="session-left">
        <span class="session-pulse">
          <span class="pulse-ring"></span>
          <span class="pulse-dot"></span>
        </span>
        <span class="session-id">Session #{{ sessionDisplayId }}</span>
        <span class="divider"></span>
        <span class="session-scenario" [class.active-mode]="activeScenarioName !== 'Free Chat'">
          <mat-icon *ngIf="activeScenarioName !== 'Free Chat'" class="scenario-icon">assignment</mat-icon>
          {{ activeScenarioName }}
        </span>
      </div>
      <div class="session-actions">
        <button 
          class="btn-run" 
          *ngIf="activeScenarioName !== 'Free Chat'" 
          (click)="runScenarioTest()" 
          [disabled]="runningScript"
          title="Run automated test script"
        >
          <mat-icon>{{ runningScript ? 'hourglass_empty' : 'play_arrow' }}</mat-icon>
          <span>{{ runningScript ? 'Running...' : 'Run Test' }}</span>
        </button>
        <button class="btn-outline" (click)="clearChat()" title="Clear chat">
          <mat-icon>restart_alt</mat-icon>
        </button>
      </div>
    </header>

    <!-- Chat Stream -->
    <div class="chat-stream" #messagesContainer>
      @if ((messages$ | async)?.length === 0) {
        <div class="welcome">
          <mat-icon class="welcome-icon">auto_stories</mat-icon>
          <h3>Welcome to Hanno Memorial Library</h3>
          <p>Inquire about our collection of synthetic titles, check availability, or explore the stacks.</p>
          <div class="suggestion-row">
            <button class="chip" (click)="sendSuggestion('Do you have books by Maren Greyhorn?')">
              Maren Greyhorn titles
            </button>
            <button class="chip" (click)="sendSuggestion('Find The Tragedy of Lorde Tuskar')">
              Lorde Tuskar lookup
            </button>
            <button class="chip" (click)="sendSuggestion('Show available noble tragedies')">
              Noble tragedies
            </button>
          </div>
        </div>
      }

      @for (message of (messages$ | async); track message.timestamp) {
        <div class="msg" [class.msg-user]="message.role === 'user'" [class.msg-agent]="message.role === 'assistant'">
          <div class="msg-bubble">
            <p class="msg-text">{{ message.content }}</p>
          </div>
        </div>
      }

      @if (loading$ | async) {
        <div class="msg msg-agent">
          <div class="msg-bubble thinking">
            <span class="dot"></span>
            <span class="dot"></span>
            <span class="dot"></span>
            <span class="thinking-text">Consulting the archives...</span>
          </div>
        </div>
      }
    </div>

    <!-- Input Area -->
    <div class="input-area">
      <form class="input-wrapper" (ngSubmit)="sendMessage()">
        <input
          type="text"
          [(ngModel)]="userInput"
          name="userInput"
          placeholder="Inquire with the librarian..."
          [disabled]="(loading$ | async) === true"
          autocomplete="off"
          class="chat-input"
        />
        <button
          type="submit"
          class="send-btn"
          [disabled]="!userInput.trim() || (loading$ | async)"
        >
          <mat-icon>play_arrow</mat-icon>
        </button>
      </form>
      <div class="input-hint">
        Press Enter to send
      </div>
    </div>
  `,
  styles: [`
    :host {
      display: flex;
      flex-direction: column;
      height: 100%;
      overflow: hidden;
    }

    /* Session Header */
    .session-header {
      height: 72px;
      border-bottom: 1px solid rgba(0,0,0,0.05);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 28px;
      background: rgba(253, 252, 248, 0.9);
      backdrop-filter: blur(8px);
      flex-shrink: 0;
      z-index: 3;
    }

    .session-left {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .session-pulse {
      position: relative;
      display: flex;
      width: 8px;
      height: 8px;
    }

    .pulse-ring {
      position: absolute;
      inset: 0;
      border-radius: 50%;
      background: var(--emerald-700);
      opacity: 0.6;
      animation: ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite;
    }

    .pulse-dot {
      position: relative;
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--emerald-800);
    }

    @keyframes ping {
      75%, 100% {
        transform: scale(2);
        opacity: 0;
      }
    }

    .session-id {
      font-family: var(--font-serif);
      font-size: 0.85rem;
      font-weight: 700;
      color: var(--stone-800);
      letter-spacing: -0.01em;
    }

    .divider {
      width: 1px;
      height: 16px;
      background: var(--stone-300);
    }

    .session-scenario {
      font-family: var(--font-serif);
      font-size: 0.78rem;
      font-style: italic;
      color: var(--stone-500);
      display: flex; align-items: center; gap: 6px;
    }
    
    .session-scenario.active-mode {
      color: var(--emerald-700); font-weight: 600;
    }

    .scenario-icon { font-size: 16px; width: 16px; height: 16px; }

    .session-actions {
      display: flex;
      gap: 6px;
    }

    .btn-outline {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 36px;
      height: 36px;
      border: none;
      background: none;
      border-radius: 4px;
      color: var(--stone-400);
      cursor: pointer;
      transition: all 0.15s ease;

      mat-icon {
        font-size: 20px;
        width: 20px;
        height: 20px;
      }

      &:hover {
        color: var(--stone-800);
        background: var(--stone-100);
      }
    }

    .btn-run {
      display: flex; align-items: center; gap: 6px; padding: 6px 12px;
      background: var(--emerald-600); color: white; border: none; border-radius: 4px;
      font-family: var(--font-serif); font-size: 0.8rem; font-weight: 600;
      cursor: pointer; transition: background 0.15s;

      mat-icon { font-size: 18px; width: 18px; height: 18px; }
      &:hover:not(:disabled) { background: var(--emerald-700); }
      &:disabled { background: var(--emerald-400); cursor: wait; }
    }

    /* Chat Stream */
    .chat-stream {
      flex: 1;
      overflow-y: auto;
      padding: 24px 28px;
      display: flex;
      flex-direction: column;
      gap: 20px;
    }

    /* Welcome */
    .welcome {
      text-align: center;
      padding: 48px 20px;
      max-width: 480px;
      margin: auto;

      .welcome-icon {
        font-size: 48px;
        width: 48px;
        height: 48px;
        color: var(--stone-400);
        margin-bottom: 16px;
      }

      h3 {
        margin: 0 0 8px;
        font-family: var(--font-serif);
        font-size: 1.15rem;
        font-weight: 700;
        color: var(--stone-800);
      }

      p {
        margin: 0 0 24px;
        font-family: var(--font-serif);
        font-size: 0.88rem;
        color: var(--stone-500);
        line-height: 1.6;
      }
    }

    .suggestion-row {
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      gap: 8px;
    }

    .chip {
      padding: 8px 16px;
      border: 1px solid var(--stone-200);
      border-radius: 4px;
      background: white;
      font-family: var(--font-serif);
      font-size: 0.78rem;
      color: var(--stone-700);
      cursor: pointer;
      transition: all 0.15s ease;

      &:hover {
        border-color: var(--stone-400);
        background: var(--stone-50);
      }
    }

    /* Messages */
    .msg {
      display: flex;
      max-width: 80%;
      animation: fadeIn 0.2s ease;
    }

    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(6px); }
      to { opacity: 1; transform: translateY(0); }
    }

    .msg-user {
      align-self: flex-end;

      .msg-bubble {
        background: var(--stone-700);
        color: var(--bg-page);
        border-radius: 2px 2px 2px 20px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.12);
      }
    }

    .msg-agent {
      align-self: flex-start;

      .msg-bubble {
        background: white;
        color: var(--stone-800);
        border: 1px solid var(--stone-200);
        border-radius: 2px 2px 20px 2px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
      }
    }

    .msg-bubble {
      padding: 14px 20px;
      font-family: var(--font-serif);
      font-size: 0.88rem;
      line-height: 1.6;
    }

    .msg-text {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
    }

    /* Thinking Indicator */
    .thinking {
      display: flex;
      align-items: center;
      gap: 4px;
      padding: 14px 20px;

      .dot {
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: var(--stone-400);
        animation: bounce 1s ease infinite;

        &:nth-child(2) { animation-delay: 150ms; }
        &:nth-child(3) { animation-delay: 300ms; }
      }

      .thinking-text {
        margin-left: 8px;
        font-family: var(--font-serif);
        font-size: 0.78rem;
        font-style: italic;
        color: var(--stone-400);
      }
    }

    @keyframes bounce {
      0%, 80%, 100% { transform: translateY(0); }
      40% { transform: translateY(-6px); }
    }

    /* Input Area */
    .input-area {
      padding: 0 28px 20px;
      flex-shrink: 0;
    }

    .input-wrapper {
      display: flex;
      align-items: center;
      padding: 6px;
      background: white;
      border: 1px solid var(--stone-200);
      border-radius: 4px;
      box-shadow: 0 4px 16px rgba(0,0,0,0.05);
      transition: border-color 0.15s ease, box-shadow 0.15s ease;

      &:focus-within {
        border-color: var(--stone-400);
        box-shadow: 0 4px 16px rgba(0,0,0,0.08);
      }
    }

    .chat-input {
      flex: 1;
      border: none;
      outline: none;
      padding: 10px 14px;
      font-family: var(--font-serif);
      font-size: 0.88rem;
      color: var(--stone-800);
      background: transparent;

      &::placeholder {
        color: var(--stone-400);
      }

      &:disabled {
        opacity: 0.5;
      }
    }

    .send-btn {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 38px;
      height: 38px;
      border: none;
      border-radius: 4px;
      background: var(--stone-800);
      color: var(--bg-page);
      cursor: pointer;
      transition: background 0.15s ease;

      mat-icon {
        font-size: 18px;
        width: 18px;
        height: 18px;
        margin-left: 2px;
      }

      &:hover:not(:disabled) {
        background: var(--stone-700);
      }

      &:disabled {
        opacity: 0.3;
        cursor: not-allowed;
      }
    }

    .input-hint {
      text-align: center;
      margin-top: 8px;
      font-family: var(--font-serif);
      font-size: 0.62rem;
      font-style: italic;
      color: var(--stone-400);
    }
  `],
})
export class ChatComponent implements AfterViewChecked, OnInit, OnDestroy {
  @ViewChild('messagesContainer') private messagesContainer?: ElementRef;

  private readonly assistantRunService = inject(AssistantRunService);
  private readonly chatService = inject(ChatService);
  private readonly benchmarkService = inject(BenchmarkService);
  private readonly subscriptions = new Subscription();

  userInput = '';
  messages$ = this.chatService.messages$;
  loading$ = this.chatService.loading$;

  sessionDisplayId = 'TRC-0001';
  activeScenarioName = '';
  runningScript = false;
  currentScriptIndex = 0;
  script: string[] = [];

  ngOnInit(): void {
    this.subscriptions.add(this.benchmarkService.activeScenario$.subscribe((s) => {
      this.activeScenarioName = s
        ? this.benchmarkService.getScenarioDisplayName(s.id)
        : 'Free Chat';

      // Update suggestions based on scenario
      if (s) {
        if (s.id.includes('author_search')) {
          this.userInput = 'Find books by Maren Greyhorn';
        } else if (s.id.includes('availability')) {
          this.userInput = 'Is The Tragedy of Lorde Tuskar available?';
        } else if (s.id.includes('ill') || s.id.includes('cross_library')) {
          this.userInput = 'I need a book that is not in this library';
        } else if (s.id.includes('patron_summary')) {
          this.userInput = 'What is my current status?';
        }
      }
    }));

    this.subscriptions.add(this.assistantRunService.scriptTriggers$.subscribe((trigger) => {
      this.startScript(trigger.script, true);
    }));

    const id = Math.floor(Math.random() * 9999)
      .toString()
      .padStart(4, '0');
    this.sessionDisplayId = `TRC-${id}`;
  }

  ngOnDestroy(): void {
    this.subscriptions.unsubscribe();
  }

  ngAfterViewChecked(): void {
    this.scrollToBottom();
  }

  sendMessage(): void {
    const message = this.userInput.trim();
    if (!message) return;
    this.userInput = '';
    this.chatService.sendMessage(message).subscribe();
  }

  sendSuggestion(suggestion: string): void {
    this.chatService.sendMessage(suggestion).subscribe();
  }

  runScenarioTest(): void {
    const scenario = this.benchmarkService.getActiveScenario();
    if (!scenario) return;

    this.startScript(this.benchmarkService.getScenarioScript(scenario.id), false);
  }

  private startScript(script: string[], resetChat: boolean): void {
    this.runningScript = false;
    this.script = [...script];
    if (resetChat) {
      this.chatService.clearChat();
    }
    if (this.script.length === 0) {
      this.userInput = 'No script defined for this scenario.';
      return;
    }

    this.currentScriptIndex = 0;
    this.runningScript = true;
    setTimeout(() => this.executeNextScriptStep(), resetChat ? 200 : 0);
  }

  private executeNextScriptStep(): void {
    if (this.currentScriptIndex >= this.script.length) {
      this.runningScript = false;
      return;
    }

    const prompt = this.script[this.currentScriptIndex];
    this.currentScriptIndex++;

    // Send the message
    this.chatService.sendMessage(prompt).subscribe({
      next: () => {
        // Wait for loading to finish, then wait a bit more, then next step
        this.waitForResponseCompletion();
      },
      error: () => this.runningScript = false
    });
  }

  private waitForResponseCompletion(): void {
    const sub = this.loading$.subscribe(isLoading => {
      if (!isLoading) {
        sub.unsubscribe();
        if (this.runningScript) {
          // Delay before next step for readability
          setTimeout(() => {
            this.executeNextScriptStep();
          }, 1500);
        }
      }
    });
  }

  clearChat(): void {
    this.runningScript = false;
    this.chatService.clearChat();
  }

  private scrollToBottom(): void {
    if (!this.messagesContainer) return;
    try {
      const el = this.messagesContainer.nativeElement as HTMLElement;
      el.scrollTop = el.scrollHeight;
    } catch {
      // Best-effort scroll.
    }
  }
}
