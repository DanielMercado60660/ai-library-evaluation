import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';

import { UserService } from '../../core/services/user.service';

@Component({
  selector: 'app-access-denied',
  standalone: true,
  imports: [CommonModule, RouterLink, MatIconModule],
  template: `
    <div class="page-container">
      <div class="card">
        <div class="icon-wrap">
          <mat-icon>lock</mat-icon>
        </div>
        <h1>Access Restricted</h1>
        <p class="reason">{{ reasonMessage }}</p>
        @if (requestedPath) {
          <p class="requested-path">Requested path: <span>{{ requestedPath }}</span></p>
        }

        <div class="actions">
          <a routerLink="/profile" class="btn btn-secondary">Go to My Account</a>
          @if (canOfferStaffSwitch) {
            <button class="btn btn-primary" (click)="switchToStaffAndRetry()">
              Switch to Staff View and Retry
            </button>
          }
        </div>
      </div>
    </div>
  `,
  styles: [`
    :host { display: block; height: 100%; overflow-y: auto; }

    .page-container {
      min-height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 32px 24px;
    }

    .card {
      width: min(680px, 100%);
      background: white;
      border: 1px solid var(--stone-200);
      border-radius: 10px;
      padding: 28px;
      text-align: center;
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
    }

    .icon-wrap {
      width: 56px;
      height: 56px;
      margin: 0 auto 16px;
      border-radius: 50%;
      background: var(--red-50);
      color: var(--red-700);
      display: flex;
      align-items: center;
      justify-content: center;

      mat-icon {
        font-size: 28px;
        width: 28px;
        height: 28px;
      }
    }

    h1 {
      margin: 0 0 8px;
      font-family: var(--font-serif);
      font-size: 1.5rem;
      color: var(--stone-800);
    }

    .reason {
      margin: 0;
      color: var(--stone-600);
      line-height: 1.5;
      font-size: 0.95rem;
    }

    .requested-path {
      margin: 14px 0 0;
      font-size: 0.84rem;
      color: var(--stone-500);

      span {
        font-family: var(--font-mono);
        background: var(--stone-100);
        padding: 2px 6px;
        border-radius: 4px;
      }
    }

    .actions {
      margin-top: 22px;
      display: flex;
      gap: 10px;
      justify-content: center;
      flex-wrap: wrap;
    }

    .btn {
      border-radius: 6px;
      padding: 9px 14px;
      font-size: 0.9rem;
      font-weight: 600;
      border: 1px solid transparent;
      text-decoration: none;
      cursor: pointer;
    }

    .btn-secondary {
      background: var(--stone-100);
      color: var(--stone-700);
      border-color: var(--stone-300);
    }

    .btn-primary {
      background: var(--stone-800);
      color: white;
      border-color: var(--stone-900);
    }
  `]
})
export class AccessDeniedComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly userService = inject(UserService);

  reasonMessage = 'You do not currently have permission to view this page.';
  requestedPath = '';
  canOfferStaffSwitch = false;

  ngOnInit(): void {
    const reason = this.route.snapshot.queryParamMap.get('reason') ?? '';
    this.requestedPath = this.route.snapshot.queryParamMap.get('from') ?? '';

    if (reason === 'staff_only') {
      this.reasonMessage = 'This page requires a staff account.';
    } else if (reason === 'profile_scope') {
      this.reasonMessage = 'You can only view your own patron profile unless you are in staff mode.';
    }

    this.canOfferStaffSwitch = reason === 'staff_only' && !this.userService.isStaff();
  }

  switchToStaffAndRetry(): void {
    this.userService.switchToEvaluationPersona('staff');
    if (this.requestedPath) {
      this.router.navigateByUrl(this.requestedPath);
      return;
    }
    this.router.navigate(['/runs']);
  }
}
