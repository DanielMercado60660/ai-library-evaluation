
import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatBadgeModule } from '@angular/material/badge';
import { MatMenuModule } from '@angular/material/menu';
import { ChatService } from '../services/chat.service';
import { CirculationService } from '../services/circulation.service';
import { UserService } from '../services/user.service';
import { NotificationService, Notification as AppNotification } from '../services/notification.service';
import { Patron, PatronCategory } from '../../shared/models/circulation.models';

@Component({
  selector: 'app-main-layout',
  standalone: true,
  imports: [
    CommonModule,
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    MatIconModule,
    MatButtonModule,
    MatBadgeModule,
    MatMenuModule
  ],
  template: `
    <div class="layout-container">
      <nav class="sidebar">
        <div class="brand">
          <div class="logo">
            <mat-icon>local_library</mat-icon>
          </div>
          <span class="brand-name">Librarian</span>
        </div>

        <div class="nav-groups">
          <div class="nav-group">
            <span class="group-label">Menu</span>
            <a routerLink="/home" routerLinkActive="active" class="nav-item">
              <mat-icon>dashboard</mat-icon>
              Dashboard
            </a>
            <a routerLink="/catalog" routerLinkActive="active" class="nav-item">
              <mat-icon>menu_book</mat-icon>
              Catalog
            </a>
            <a routerLink="/chat" routerLinkActive="active" class="nav-item">
              <mat-icon>chat</mat-icon>
              Assistant
            </a>
            @if (userService.isStaff()) {
              <a routerLink="/patrons" routerLinkActive="active" class="nav-item">
                <mat-icon>people</mat-icon>
                Patrons
              </a>
            }
          </div>

          <div class="nav-group">
            <span class="group-label">Analytics</span>
            <a routerLink="/runs" routerLinkActive="active" class="nav-item">
              <mat-icon>science</mat-icon>
              Benchmarks
            </a>
            <a routerLink="/analytics" routerLinkActive="active" class="nav-item">
              <mat-icon>analytics</mat-icon>
              Analytics
            </a>
          </div>
        </div>

        <div class="user-profile">
          <a routerLink="/profile" routerLinkActive="active" class="profile-link">
            <div class="avatar">{{ userService.currentUser().avatarInitials }}</div>
            <div class="user-info">
              <span class="name">{{ userService.currentUser().name }}</span>
              <div class="role-badge">
                <span class="role">{{ userService.currentUser().role | titlecase }}</span>
                @if (userService.isStaff()) {
                  <span class="staff-tag">STAFF</span>
                }
              </div>
            </div>
            <mat-icon class="chevron">chevron_right</mat-icon>
          </a>
        </div>
      </nav>

      <main class="content-area">
        <header class="top-bar">
          <div class="breadcrumbs">
            <!-- Breadcrumbs could be dynamic here -->
            <span class="crumb">Library</span>
            <mat-icon>chevron_right</mat-icon>
            <span class="crumb active">Home</span>
          </div>
          
          <div class="actions">
            @if (patronOptions.length > 0) {
              <div class="quick-patron-switch">
                <label for="quick-patron-select">Patron</label>
                <select
                  id="quick-patron-select"
                  [value]="userService.currentUser().id"
                  (change)="onQuickPatronSwitch($event)"
                >
                  @for (patron of patronOptions; track patron.id) {
                    <option [value]="patron.id">{{ patron.name }}</option>
                  }
                </select>
              </div>
            }
            <button
              mat-icon-button
              [matMenuTriggerFor]="notificationMenu"
              [matBadge]="unreadNotificationCount"
              [matBadgeHidden]="unreadNotificationCount === 0"
              matBadgeColor="warn"
              matBadgeSize="small"
              aria-label="Notifications"
            >
              <mat-icon>notifications</mat-icon>
            </button>

            <mat-menu #notificationMenu="matMenu" xPosition="before">
              <button mat-menu-item disabled>
                <mat-icon>notifications</mat-icon>
                <span>Notifications</span>
              </button>

              @if (unreadNotificationCount > 0) {
                <button mat-menu-item (click)="markAllNotificationsRead()">
                  <mat-icon>done_all</mat-icon>
                  <span>Mark all as read</span>
                </button>
              }

              @if (notifications.length === 0) {
                <button mat-menu-item disabled>
                  <mat-icon>inbox</mat-icon>
                  <span>No notifications</span>
                </button>
              } @else {
                @for (notification of notifications; track notification.id) {
                  <button mat-menu-item (click)="openNotification(notification)">
                    <mat-icon>{{ notification.read ? 'drafts' : 'mark_email_unread' }}</mat-icon>
                    <span>{{ notification.title }}</span>
                  </button>
                }
              }
            </mat-menu>

            <button mat-icon-button>
              <mat-icon>help_outline</mat-icon>
            </button>
          </div>
        </header>

        <div class="scrollable-content">
          <router-outlet></router-outlet>
        </div>
      </main>
    </div>
  `,
  styles: [`
    :host { display: block; height: 100vh; overflow: hidden; }

    .layout-container {
      display: flex; height: 100%; width: 100%;
      background: var(--bg-page, #f8fafc);
    }

    /* Sidebar Styles */
    .sidebar {
      width: 260px; background: white; border-right: 1px solid var(--stone-200);
      display: flex; flex-direction: column; flex-shrink: 0;
    }

    .brand {
      height: 64px; display: flex; align-items: center; gap: 12px; padding: 0 24px;
      border-bottom: 1px solid var(--stone-100);
      .logo {
        width: 32px; height: 32px; background: var(--primary, #4f46e5); color: white;
        border-radius: 8px; display: flex; align-items: center; justify-content: center;
        mat-icon { font-size: 20px; width: 20px; height: 20px; }
      }
      .brand-name { font-family: var(--font-serif); font-weight: 700; font-size: 1.1rem; color: var(--stone-800); }
    }

    .nav-groups { flex: 1; padding: 24px 16px; overflow-y: auto; }

    .nav-group {
      margin-bottom: 32px;
      .group-label {
        display: block; padding: 0 12px; margin-bottom: 8px;
        font-size: 0.7rem; font-weight: 700; text-transform: uppercase; color: var(--stone-400); letter-spacing: 0.05em;
      }
    }

    .nav-item {
      display: flex; align-items: center; gap: 12px; padding: 10px 12px;
      border-radius: 6px; color: var(--stone-600); text-decoration: none;
      font-size: 0.9rem; font-weight: 500; transition: all 0.15s;
      margin-bottom: 2px;
      
      mat-icon { font-size: 20px; width: 20px; height: 20px; color: var(--stone-400); }

      &:hover { background: var(--stone-50); color: var(--stone-900); mat-icon { color: var(--stone-600); } }
      &.active {
        background: var(--indigo-50); color: var(--indigo-700);
        mat-icon { color: var(--indigo-600); }
      }
    }

    .user-profile {
      padding: 16px; border-top: 1px solid var(--stone-100);
      .profile-link {
        display: flex; align-items: center; gap: 12px; padding: 8px;
        border-radius: 8px; text-decoration: none; transition: background 0.15s;
        &:hover { background: var(--stone-50); }
        &.active { background: var(--stone-100); }
      }
      .avatar {
        width: 36px; height: 36px; background: var(--stone-200); border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-weight: 600; font-size: 0.8rem; color: var(--stone-600);
      }
      .user-info { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
      .name { font-weight: 600; font-size: 0.9rem; color: var(--stone-800); }
      .role-badge { display: flex; align-items: center; gap: 6px; }
      .role { font-size: 0.75rem; color: var(--stone-500); }
      .staff-tag {
        font-size: 0.6rem; font-weight: 700; color: white; background: var(--violet-600);
        padding: 1px 4px; border-radius: 3px; letter-spacing: 0.05em;
      }
      .chevron { color: var(--stone-400); font-size: 20px; }
    }

    /* Content Area Styles */
    .content-area { flex: 1; display: flex; flex-direction: column; overflow: hidden; position: relative; }

    .top-bar {
      height: 64px; background: white; border-bottom: 1px solid var(--stone-200);
      display: flex; align-items: center; justify-content: space-between; padding: 0 32px;
      flex-shrink: 0;
    }

    .breadcrumbs {
      display: flex; align-items: center; gap: 8px; font-size: 0.9rem; color: var(--stone-500);
      mat-icon { font-size: 16px; width: 16px; height: 16px; opacity: 0.5; }
      .crumb { font-weight: 500; }
      .crumb.active { color: var(--stone-900); }
    }

    .actions {
      display: flex;
      gap: 8px;
      align-items: center;
      mat-icon { color: var(--stone-400); }
    }

    .quick-patron-switch {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-right: 6px;

      label {
        font-size: 0.66rem;
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
        font-size: 0.82rem;
        padding: 6px 8px;
        max-width: 210px;
      }
    }

    .scrollable-content { flex: 1; overflow-y: auto; padding: 0; }
  `]
})
export class MainLayoutComponent implements OnInit {
  readonly userService = inject(UserService);
  private readonly chatService = inject(ChatService);
  private readonly notificationService = inject(NotificationService);
  private readonly circulationService = inject(CirculationService);

  patronOptions: Patron[] = [];

  ngOnInit(): void {
    this.circulationService.getPatrons().subscribe({
      next: (patrons) => {
        this.patronOptions = patrons;
      },
      error: () => {
        this.patronOptions = [];
      },
    });
  }

  get notifications(): AppNotification[] {
    return this.notificationService
      .getNotifications(this.userService.currentUser().id)
      .slice(0, 8);
  }

  get unreadNotificationCount(): number {
    return this.notifications.filter((notification) => !notification.read).length;
  }

  openNotification(notification: AppNotification): void {
    if (!notification.read) {
      this.notificationService.markAsRead(notification.id);
    }
  }

  markAllNotificationsRead(): void {
    this.notificationService.markAllAsRead(this.userService.currentUser().id);
  }

  onQuickPatronSwitch(event: Event): void {
    const target = event.target as HTMLSelectElement | null;
    const patronId = target?.value ?? '';
    if (!patronId || patronId === this.userService.currentUser().id) return;

    const selected = this.patronOptions.find((patron) => patron.id === patronId);
    if (!selected) return;

    const switchMode = this.promptPatronSwitchMode(selected.name);
    if (!switchMode) {
      if (target) {
        target.value = this.userService.currentUser().id;
      }
      return;
    }

    if (switchMode === 'fresh') {
      this.chatService.clearChat();
    } else {
      this.chatService.rotateSession();
    }

    const initials = selected.name
      .split(' ')
      .map((part) => part[0] ?? '')
      .join('')
      .slice(0, 2)
      .toUpperCase();

    this.userService.setCurrentUser({
      id: selected.id,
      name: selected.name,
      role: selected.category === PatronCategory.STAFF ? 'staff' : 'patron',
      avatarInitials: initials || 'PL',
    });
  }

  private promptPatronSwitchMode(nextPatronName: string): 'fresh' | 'keep' | null {
    const response = window.prompt(
      `Switch active profile to ${nextPatronName}?\n\n` +
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
