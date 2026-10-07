import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatIconModule } from '@angular/material/icon';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { UserService } from '../../core/services/user.service';
import { RouterModule } from '@angular/router';
import { CirculationService } from '../../core/services/circulation.service';
import { Patron, PatronCategory } from '../../shared/models/circulation.models';

@Component({
  selector: 'app-patron-list',
  standalone: true,
  imports: [CommonModule, RouterModule, MatIconModule, MatSnackBarModule],
  template: `
    <div class="patron-list-container">
      <header class="page-header">
        <h1>Patron Directory</h1>
        <p class="subtitle">Manage and view library patrons</p>
      </header>

      <div class="card">
        <div class="table-container">
          <table class="data-table">
            <thead>
              <tr>
                <th>Barcode</th>
                <th>Name</th>
                <th>Email</th>
                <th>Category</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr *ngFor="let patron of patrons">
                <td class="font-mono">{{ patron.barcode }}</td>
                <td>
                  <div class="patron-name">{{ patron.name }}</div>
                  <div class="patron-phone">{{ patron.phone }}</div>
                </td>
                <td>{{ patron.email }}</td>
                <td><span class="badge" [ngClass]="'badge-' + patron.category">{{ patron.category }}</span></td>
                <td>
                  <span class="status-indicator" [ngClass]="patron.blocked ? 'status-blocked' : 'status-active'">
                    {{ patron.blocked ? 'Blocked' : 'Active' }}
                  </span>
                </td>
                <td>
                  <div class="actions">
                    <button class="btn btn-sm btn-ghost" (click)="impersonate(patron)">
                      <mat-icon>login</mat-icon>
                    </button>
                    <a [routerLink]="['/profile', patron.id]" class="btn btn-sm btn-outline">View Profile</a>
                  </div>
                </td>
              </tr>
              <tr *ngIf="patrons.length === 0 && !loading">
                <td colspan="6" class="text-center py-8 text-muted">No patrons found.</td>
              </tr>
              <tr *ngIf="loading">
                <td colspan="6" class="text-center py-8">Loading patrons...</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .patron-list-container {
      max-width: 1200px;
      margin: 0 auto;
    }
    
    .page-header {
      margin-bottom: 2rem;
    }
    
    .subtitle {
      color: var(--text-secondary);
      margin-top: 0.5rem;
    }

    .table-container {
      overflow-x: auto;
    }

    .data-table {
      width: 100%;
      border-collapse: collapse;
    }

    .data-table th, .data-table td {
      padding: 1rem;
      text-align: left;
      border-bottom: 1px solid var(--border-color);
    }

    .data-table th {
      background-color: var(--surface-hover);
      font-weight: 600;
      color: var(--text-primary);
    }

    .data-table tr:hover {
      background-color: var(--surface-hover);
    }

    .patron-phone {
      font-size: 0.875rem;
      color: var(--text-secondary);
    }

    .font-mono {
      font-family: monospace;
    }

    .badge {
      display: inline-block;
      padding: 0.25rem 0.75rem;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 500;
      text-transform: capitalize;
      background-color: var(--surface-hover);
      color: var(--text-secondary);
    }

    .badge-adult { background-color: #e3f2fd; color: #1565c0; }
    .badge-youth { background-color: #e8f5e9; color: #2e7d32; }
    .badge-staff { background-color: #f3e5f5; color: #7b1fa2; }
    .badge-researcher { background-color: #e0f7fa; color: #006064; }
    .badge-restricted { background-color: #ffebee; color: #b71c1c; }

    .status-indicator {
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      font-size: 0.875rem;
    }

    .status-indicator::before {
      content: '';
      display: block;
      width: 8px;
      height: 8px;
      border-radius: 50%;
    }

    .status-active::before { background-color: var(--success-color); }
    .status-blocked::before { background-color: var(--error-color); }
    .status-blocked { color: var(--error-color); }

    .actions { display: flex; align-items: center; gap: 8px; }
    
    .btn-ghost {
      background: transparent; border: none; padding: 4px; border-radius: 4px;
      color: var(--text-secondary); cursor: pointer; display: flex; align-items: center; justify-content: center;
      &:hover { background: var(--surface-hover); color: var(--text-primary); }
      mat-icon { font-size: 18px; width: 18px; height: 18px; }
    }
  `]
})
export class PatronListComponent implements OnInit {
  patrons: Patron[] = [];
  loading = true;

  private circulationService = inject(CirculationService);
  private userService = inject(UserService);
  private snackBar = inject(MatSnackBar);

  ngOnInit(): void {
    this.circulationService.getPatrons().subscribe({
      next: (data) => {
        this.patrons = data;
        this.loading = false;
      },
      error: (err) => {
        console.error('Error loading patrons', err);
        this.loading = false;
      }
    });
  }

  impersonate(patron: Patron) {
    // Generate initials
    const initials = patron.name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase();

    this.userService.setCurrentUser({
      id: patron.id,
      name: patron.name,
      role: patron.category === PatronCategory.STAFF ? 'staff' : 'patron',
      avatarInitials: initials
    });

    this.snackBar.open(`Now viewing as ${patron.name}`, 'Close', { duration: 3000 });
  }
}
