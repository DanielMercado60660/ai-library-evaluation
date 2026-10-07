
import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';
import { MatTabsModule } from '@angular/material/tabs';

import { ChatService } from '../../core/services/chat.service';
import { CirculationService } from '../../core/services/circulation.service';
import { Patron, PatronCategory, PatronSummaryResponse } from '../../shared/models/circulation.models';
import { ILLService, ILLRequest } from '../../core/services/ill.service';
import { NotificationService, Notification as AppNotification } from '../../core/services/notification.service';
import { UserPermission, UserService } from '../../core/services/user.service';

@Component({
  selector: 'app-patron-profile',
  standalone: true,
  imports: [CommonModule, MatIconModule, MatTabsModule],
  template: `
    <div class="page-container">
      <div class="header">
        <h1><mat-icon>account_circle</mat-icon> My Account</h1>

        <div class="profile-controls">
          <div class="persona-toggle">
            <label>Evaluation Role</label>
            <div class="persona-buttons">
              @for (persona of userService.evaluationPersonas; track persona.role) {
                <button
                  type="button"
                  class="persona-btn"
                  [class.active]="isActivePersona(persona.role)"
                  (click)="onPersonaSwitch(persona.role)"
                >
                  {{ persona.role | titlecase }}
                </button>
              }
            </div>
          </div>

          <div class="patron-switcher">
            <label for="patron-switcher-select">Active Patron Profile</label>
            @if (patronOptionsLoading) {
              <p class="patron-switcher-loading">Loading patrons...</p>
            } @else {
              <select
                id="patron-switcher-select"
                [value]="currentPatronId"
                [disabled]="loading || patronOptions.length === 0"
                (change)="onPatronSelectionChange($event)"
              >
                @for (patron of patronOptions; track patron.id) {
                  <option [value]="patron.id">{{ patron.name }} ({{ patron.category }})</option>
                }
              </select>
            }
          </div>
        </div>
      </div>

      @if (loading) {
        <div class="loading-state"><p>Loading account details...</p></div>
      } @else if (error) {
        <div class="error-state">
          <mat-icon>error_outline</mat-icon>
          <p>{{ error }}</p>
        </div>
      } @else if (summary) {
        <div class="patron-card">
          <div class="patron-info">
            <h2>{{ summary.patron.name }}</h2>
            <p class="patron-id">ID: {{ summary.patron.id }}</p>
            <p class="patron-email">{{ summary.patron.email }}</p>
            <div class="patron-status">
              <span class="badge" [class.blocked]="summary.patron.blocked">
                {{ summary.patron.blocked ? 'Blocked' : 'Active' }}
              </span>
              <span class="badge category">{{ summary.patron.category }}</span>
            </div>
            <div class="permissions-row">
              <span class="permissions-label">Effective Permissions</span>
              <div class="permissions-list">
                @for (permission of effectivePermissions; track permission.id) {
                  <span class="permission-pill" [class.enabled]="permission.enabled">
                    {{ permission.label }}
                  </span>
                }
              </div>
            </div>
          </div>
          <div class="patron-stats">
            <div class="stat">
              <span class="value">{{ summary.checkouts.length }}</span>
              <span class="label">Checkouts</span>
            </div>
            <div class="stat">
              <span class="value">{{ summary.holds.length }}</span>
              <span class="label">Holds</span>
            </div>
            <div class="stat">
              <span class="value" [class.negative]="summary.total_fines_owed > 0">
                \${{ summary.total_fines_owed.toFixed(2) }}
              </span>
              <span class="label">Fines</span>
            </div>
          </div>
        </div>

        <mat-tab-group animationDuration="0ms">
          <mat-tab label="Checkouts ({{ summary.checkouts.length }})">
            <div class="list-container">
              @if (summary.checkouts.length === 0) {
                <div class="empty-list">No active checkouts.</div>
              } @else {
                @for (checkout of summary.checkouts; track checkout.id) {
                  <div class="list-item checkout-card" [class.overdue]="checkout.status === 'overdue'">
                    <div class="item-icon">
                      <mat-icon>book</mat-icon>
                    </div>
                    <div class="item-details">
                      <h3>Book ID: {{ checkout.instance_id }}</h3>
                      <p class="due-date">
                        Due: <strong>{{ checkout.due_date | date:'mediumDate' }}</strong>
                        @if (checkout.status === 'overdue') {
                          <span class="overdue-tag">OVERDUE</span>
                        }
                      </p>
                      <p class="checkout-date">Checked out: {{ checkout.checked_out_at | date:'mediumDate' }}</p>
                    </div>
                    <div class="item-actions">
                      <button class="action-btn" (click)="renew(checkout.id)">
                        <mat-icon>autorenew</mat-icon> Renew
                      </button>
                    </div>
                  </div>
                }
              }
            </div>
          </mat-tab>

          <mat-tab label="Holds ({{ summary.holds.length }})">
            <div class="list-container">
              @if (summary.holds.length === 0) {
                <div class="empty-list">No active holds.</div>
              } @else {
                @for (hold of summary.holds; track hold.id) {
                  <div class="list-item hold-card">
                    <div class="item-icon">
                      <mat-icon>hourglass_empty</mat-icon>
                    </div>
                    <div class="item-details">
                      <h3>Book ID: {{ hold.book_id }}</h3>
                      <p class="hold-position">Queue Position: <strong>{{ hold.position }}</strong></p>
                      <p class="hold-status">Status: {{ hold.status }}</p>
                    </div>
                  </div>
                }
              }
            </div>
          </mat-tab>

          <mat-tab label="Fines (\${{ summary.total_fines_owed.toFixed(2) }})">
            <div class="list-container">
              @if (summary.fines.length === 0) {
                <div class="empty-list">No unpaid fines.</div>
              } @else {
                @for (fine of summary.fines; track fine.id) {
                  <div class="list-item fine-card">
                    <div class="item-icon">
                      <mat-icon>attach_money</mat-icon>
                    </div>
                    <div class="item-details">
                      <h3>{{ fine.reason | titlecase }}</h3>
                      <p class="fine-desc">{{ fine.description }}</p>
                      <p class="fine-date">{{ fine.created_at | date:'mediumDate' }}</p>
                    </div>
                    <div class="fine-amount">
                      -\${{ fine.amount.toFixed(2) }}
                    </div>
                  </div>
                }
              }
            </div>
          </mat-tab>

          <mat-tab label="My Requests ({{ illRequests.length }})">
            <div class="list-container">
              @if (illRequests.length === 0) {
                <div class="empty-list">No active ILL requests.</div>
              } @else {
                @for (req of illRequests; track req.id) {
                  <div class="list-item request-card" [class.shipped]="req.status === 'shipped'">
                    <div class="item-icon">
                      <mat-icon>local_shipping</mat-icon>
                    </div>
                    <div class="item-details">
                      <h3>{{ req.book_title || 'Unknown Title' }}</h3>
                      <p class="req-id">Request ID: {{ req.id }}</p>
                      <p class="req-status">Status: <strong>{{ req.status | uppercase }}</strong></p>
                      <p class="req-date">Requested: {{ req.requested_at | date:'mediumDate' }}</p>
                    </div>
                  </div>
                }
              }
            </div>
          </mat-tab>

          <mat-tab label="Notifications ({{ unreadNotificationCount }})">
            <div class="list-container">
              <div class="notifications-header">
                <h3>Recent Notifications</h3>
                @if (unreadNotificationCount > 0) {
                  <button class="action-btn" (click)="markAllNotificationsRead()">
                    <mat-icon>done_all</mat-icon> Mark all as read
                  </button>
                }
              </div>

              @if (notifications.length === 0) {
                <div class="empty-list">No notifications for this patron.</div>
              } @else {
                <div class="notification-list">
                  @for (notification of notifications; track notification.id) {
                    <div class="notification-item" [class.unread]="!notification.read">
                      <div
                        class="notif-icon"
                        [class.info]="notification.type === 'info'"
                        [class.success]="notification.type === 'success'"
                        [class.warning]="notification.type === 'warning'"
                      >
                        <mat-icon>{{ notification.read ? 'drafts' : 'mark_email_unread' }}</mat-icon>
                      </div>
                      <div class="notif-content">
                        <div class="notif-header">
                          <span class="notif-title">{{ notification.title }}</span>
                          <span class="notif-time">{{ notification.timestamp | date:'short' }}</span>
                        </div>
                        <p class="notif-message">{{ notification.message }}</p>
                      </div>
                      @if (!notification.read) {
                        <button class="action-btn" (click)="markNotificationRead(notification.id)">
                          <mat-icon>check</mat-icon> Mark Read
                        </button>
                      }
                    </div>
                  }
                </div>
              }
            </div>
          </mat-tab>
        </mat-tab-group>
      }
    </div>
  `,
  styles: [`
    :host { display: block; height: 100%; overflow-y: auto; }
    .page-container { max-width: 960px; margin: 0 auto; padding: 32px 24px; }

    .header {
      margin-bottom: 24px;
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 16px;
      flex-wrap: wrap;
    }

    .profile-controls {
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: 12px;
    }

    .persona-toggle {
      display: flex;
      flex-direction: column;
      gap: 6px;
      min-width: 220px;

      label {
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--stone-500);
        font-weight: 700;
      }
    }

    .persona-buttons {
      display: inline-flex;
      border: 1px solid var(--stone-300);
      border-radius: 6px;
      overflow: hidden;
      width: fit-content;
    }

    .persona-btn {
      border: none;
      background: white;
      color: var(--stone-600);
      padding: 8px 14px;
      font-size: 0.85rem;
      font-weight: 600;
      cursor: pointer;

      &:not(:last-child) {
        border-right: 1px solid var(--stone-200);
      }

      &.active {
        background: var(--stone-800);
        color: white;
      }
    }

    .patron-switcher {
      display: flex;
      flex-direction: column;
      gap: 6px;
      min-width: 280px;

      label {
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--stone-500);
        font-weight: 700;
      }

      select {
        border: 1px solid var(--stone-300);
        border-radius: 6px;
        background: white;
        color: var(--stone-700);
        font-size: 0.9rem;
        padding: 8px 10px;
      }
    }

    .patron-switcher-loading {
      margin: 0;
      font-size: 0.85rem;
      color: var(--stone-500);
      font-style: italic;
    }

    h1 {
      display: flex; align-items: center; gap: 10px;
      font-family: var(--font-serif); font-size: 1.8rem; font-weight: 700;
      color: var(--stone-800); margin: 0;
      mat-icon { font-size: 32px; width: 32px; height: 32px; color: var(--stone-500); }
    }

    .loading-state, .error-state {
      text-align: center; padding: 60px 20px; color: var(--stone-400);
      mat-icon { font-size: 40px; width: 40px; height: 40px; margin-bottom: 12px; }
    }

    .patron-card {
      background: white; border: 1px solid var(--stone-200); border-radius: 8px;
      padding: 24px; margin-bottom: 32px; display: flex; justify-content: space-between;
      gap: 24px; box-shadow: 0 2px 4px rgba(0,0,0,0.02);
      
      @media (max-width: 600px) { flex-direction: column; }
    }

    .patron-info {
      h2 { margin: 0 0 4px 0; font-family: var(--font-serif); font-size: 1.4rem; color: var(--stone-900); }
      .patron-id { font-family: var(--font-mono); font-size: 0.8rem; color: var(--stone-400); margin: 0; }
      .patron-email { color: var(--stone-600); margin: 4px 0 12px 0; }
    }

    .patron-status {
      display: flex; gap: 8px;
      .badge {
        padding: 4px 10px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase;
        background: var(--emerald-50); color: var(--emerald-800);
        &.blocked { background: var(--red-50); color: var(--red-800); }
        &.category { background: var(--blue-50); color: var(--blue-800); }
      }
    }

    .permissions-row {
      margin-top: 12px;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .permissions-label {
      font-size: 0.72rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--stone-500);
      font-weight: 700;
    }

    .permissions-list {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }

    .permission-pill {
      border: 1px solid var(--stone-300);
      border-radius: 999px;
      padding: 3px 9px;
      font-size: 0.72rem;
      color: var(--stone-500);
      background: var(--stone-50);
    }

    .permission-pill.enabled {
      border-color: var(--emerald-300);
      color: var(--emerald-800);
      background: var(--emerald-50);
    }

    .patron-stats {
      display: flex; gap: 32px; align-items: center;
      .stat {
        display: flex; flex-direction: column; align-items: center;
        .value { font-size: 1.8rem; font-weight: 700; color: var(--stone-800); font-family: var(--font-mono); }
        .value.negative { color: var(--red-700); }
        .label { font-size: 0.75rem; text-transform: uppercase; color: var(--stone-400); font-weight: 600; }
      }
    }

    .list-container { padding: 24px 0; }
    .empty-list { text-align: center; color: var(--stone-400); padding: 32px; font-style: italic; }

    .list-item {
      display: flex; align-items: center; gap: 16px; padding: 16px;
      border: 1px solid var(--stone-200); border-radius: 8px; margin-bottom: 12px;
      background: white; transition: all 0.2s;
      
      &:hover { border-color: var(--stone-300); box-shadow: 0 2px 8px rgba(0,0,0,0.03); }

      .item-icon {
        width: 40px; height: 40px; border-radius: 50%; background: var(--stone-50);
        display: flex; align-items: center; justify-content: center;
        mat-icon { color: var(--stone-400); }
      }
      
      .item-details { flex: 1; }
      
      h3 { margin: 0 0 4px 0; font-size: 1rem; font-weight: 600; color: var(--stone-800); }
      p { margin: 0; font-size: 0.85rem; color: var(--stone-500); }
    }

    .checkout-card {
      &.overdue {
        border-color: var(--red-200); background: var(--red-50);
        .item-icon { background: var(--red-100); mat-icon { color: var(--red-500); } }
      }
      .overdue-tag {
        font-size: 0.7rem; background: var(--red-600); color: white;
        padding: 2px 6px; border-radius: 2px; margin-left: 8px; font-weight: 700;
      }
    }

    .fine-card {
      .fine-amount { font-family: var(--font-mono); font-weight: 700; color: var(--red-700); font-size: 1rem; }
    }

    .request-meta span { display: flex; align-items: center; gap: 4px; }
    
    /* Notifications */
    .notifications-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 12px;

      h3 {
        margin: 0;
        font-size: 1rem;
        font-weight: 600;
        color: var(--stone-700);
      }
    }

    .notification-list { display: flex; flex-direction: column; gap: 12px; }
    .notification-item {
      display: flex; gap: 12px; padding: 12px; border-radius: 8px;
      background: var(--bg-page); border: 1px solid var(--border-color);
    }
    .notification-item.unread { background: white; border-color: var(--stone-300); box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
    .notif-icon {
      flex-shrink: 0; width: 32px; height: 32px; border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
    }
    .notif-icon.info { background: var(--blue-50); color: var(--blue-700); }
    .notif-icon.success { background: var(--emerald-50); color: var(--emerald-700); }
    .notif-icon.warning { background: var(--amber-50); color: var(--amber-700); }
    .notif-content { flex: 1; }
    .notif-header { display: flex; justify-content: space-between; margin-bottom: 4px; }
    .notif-title { font-weight: 600; font-size: 0.9rem; color: var(--stone-900); }
    .notif-time { font-size: 0.75rem; color: var(--stone-400); }
    .notif-message { font-size: 0.85rem; color: var(--stone-600); margin: 0; line-height: 1.4; }
    .action-btn {
      display: flex; align-items: center; gap: 6px;
      padding: 8px 12px; border: 1px solid var(--stone-300); border-radius: 4px;
      background: white; font-size: 0.85rem; font-weight: 600; color: var(--stone-700);
      cursor: pointer; transition: all 0.15s;
      
      &:hover { background: var(--stone-50); border-color: var(--stone-400); }
      mat-icon { font-size: 18px; width: 18px; height: 18px; }
    }

    .request-card {
      .req-id { font-family: var(--font-mono); font-size: 0.75rem; color: var(--stone-400); margin-bottom: 4px; }
      .req-status { margin-bottom: 4px; }
      &.shipped {
        border-color: var(--blue-200); background: var(--blue-50);
        .item-icon { background: var(--blue-100); mat-icon { color: var(--blue-500); } }
      }
    }
  `]
})
export class PatronProfileComponent implements OnInit {
  private chatService = inject(ChatService);
  private circulationService = inject(CirculationService);
  private illService = inject(ILLService);
  private notificationService = inject(NotificationService);
  readonly userService = inject(UserService);
  private router = inject(Router);

  summary: PatronSummaryResponse | null = null;
  illRequests: ILLRequest[] = [];
  notifications: AppNotification[] = [];
  patronOptions: Patron[] = [];
  patronOptionsLoading = false;
  loading = true;
  error: string | null = null;

  currentPatronId = this.userService.currentUser().id;

  private route = inject(ActivatedRoute);

  get unreadNotificationCount(): number {
    return this.notifications.filter((notification) => !notification.read).length;
  }

  get effectivePermissions(): UserPermission[] {
    return this.userService.getEffectivePermissions();
  }

  ngOnInit() {
    this.loadPatronOptions();

    this.route.paramMap.subscribe(params => {
      const id = params.get('id');
      this.currentPatronId = id ?? this.userService.currentUser().id;
      this.syncCurrentUserFromActivePatron();

      this.loadData();
    });
  }

  loadData() {
    this.loading = true;

    // Load patron summary
    this.circulationService.getPatronSummary(this.currentPatronId).subscribe({
      next: (data) => {
        this.summary = data;
        this.loading = false;

        // Load additional data
        this.loadRequests();
        this.loadNotifications();
      },
      error: (err) => {
        this.error = 'Failed to load account details.';
        this.loading = false;
      }
    });
  }

  loadRequests() {
    this.illService.getRequests(this.currentPatronId).subscribe({
      next: (data) => this.illRequests = data,
      error: (err) => console.error('Failed to load ILL requests', err)
    });
  }

  loadNotifications() {
    this.notifications = this.notificationService.getNotifications(this.currentPatronId);
  }

  markNotificationRead(notificationId: string): void {
    this.notificationService.markAsRead(notificationId);
    this.loadNotifications();
  }

  markAllNotificationsRead(): void {
    this.notificationService.markAllAsRead(this.currentPatronId);
    this.loadNotifications();
  }

  renew(checkoutId: string) {
    if (!confirm('Renew this item?')) return;

    this.circulationService.renewCheckout(checkoutId).subscribe({
      next: () => {
        this.loadData(); // Reload to show new date
      },
      error: (err) => {
        alert('Failed to renew item: ' + (err.error?.detail?.message || 'Unknown error'));
      }
    });
  }

  onPatronSelectionChange(event: Event): void {
    const target = event.target as HTMLSelectElement | null;
    const selectedPatronId = target?.value ?? '';
    if (!selectedPatronId || selectedPatronId === this.currentPatronId) return;

    const selectedPatron = this.patronOptions.find((patron) => patron.id === selectedPatronId);
    if (!selectedPatron) return;

    const switchMode = this.promptPatronSwitchMode(selectedPatron.name);
    if (!switchMode) {
      if (target) {
        target.value = this.currentPatronId;
      }
      return;
    }

    if (switchMode === 'fresh') {
      this.chatService.clearChat();
    } else {
      this.chatService.rotateSession();
    }

    this.setCurrentUserFromPatron(selectedPatron);
    this.router.navigate(['/profile', selectedPatronId]);
  }

  private loadPatronOptions(): void {
    this.patronOptionsLoading = true;
    this.circulationService.getPatrons().subscribe({
      next: (patrons) => {
        this.patronOptions = patrons;
        this.patronOptionsLoading = false;
        this.syncCurrentUserFromActivePatron();
      },
      error: () => {
        this.patronOptions = [];
        this.patronOptionsLoading = false;
      },
    });
  }

  onPersonaSwitch(role: 'patron' | 'staff'): void {
    if (this.userService.currentUser().role === role) return;

    const label = role === 'staff' ? 'Staff persona' : 'Patron persona';
    const switchMode = this.promptPatronSwitchMode(label);
    if (!switchMode) {
      return;
    }

    if (switchMode === 'fresh') {
      this.chatService.clearChat();
    } else {
      this.chatService.rotateSession();
    }

    this.userService.switchToEvaluationPersona(role);
    const switchedUser = this.userService.currentUser();
    this.currentPatronId = switchedUser.id;
    this.router.navigate(['/profile', switchedUser.id]);
  }

  isActivePersona(role: 'patron' | 'staff'): boolean {
    return this.userService.currentUser().role === role;
  }

  private syncCurrentUserFromActivePatron(): void {
    const activePatron = this.patronOptions.find((patron) => patron.id === this.currentPatronId);
    if (!activePatron) return;
    this.setCurrentUserFromPatron(activePatron);
  }

  private setCurrentUserFromPatron(patron: Patron): void {
    const initials = patron.name
      .split(' ')
      .map((part) => part[0] ?? '')
      .join('')
      .slice(0, 2)
      .toUpperCase();

    this.userService.setCurrentUser({
      id: patron.id,
      name: patron.name,
      role: patron.category === PatronCategory.STAFF ? 'staff' : 'patron',
      avatarInitials: initials || 'PL',
    });
  }

  private promptPatronSwitchMode(nextProfileName: string): 'fresh' | 'keep' | null {
    const response = window.prompt(
      `Switch active profile to ${nextProfileName}?\n\n` +
        "Type one option:\n" +
        "- fresh (Start fresh: clear transcript + new session)\n" +
        "- keep (Keep transcript: preserve messages + new backend session)\n" +
        "- cancel",
      'fresh',
    );
    if (response === null) {
      return null;
    }

    const normalized = response.trim().toLowerCase();
    if (normalized === 'fresh') return 'fresh';
    if (normalized === 'keep') return 'keep';
    return null;
  }
}
