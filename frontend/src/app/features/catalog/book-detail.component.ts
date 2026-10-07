
import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';

import { CatalogService } from '../../core/services/catalog.service';
import { ILLService, ILLSourceLibrary } from '../../core/services/ill.service';
import { UserService } from '../../core/services/user.service';
import { BookDetailResponse } from '../../shared/models/catalog.models';

@Component({
  selector: 'app-book-detail',
  standalone: true,
  imports: [CommonModule, RouterLink, MatIconModule, MatButtonModule, MatSnackBarModule],
  template: `
    <div class="page-container">
      <a routerLink="/catalog" class="back-link">
        <mat-icon>arrow_back</mat-icon> Back to Catalog
      </a>

      @if (loading) {
        <div class="loading-state"><p>Loading book details...</p></div>
      } @else if (error) {
        <div class="error-state">
          <mat-icon>error_outline</mat-icon>
          <p>{{ error }}</p>
        </div>
      } @else if (bookDetail) {
        <div class="book-header">
          <div class="book-cover-placeholder">
            <mat-icon>book</mat-icon>
          </div>
          <div class="book-info">
            <h1>{{ bookDetail.book.title }}</h1>
            <p class="author">By {{ bookDetail.book.author }}</p>
            <div class="meta-row">
              <span class="pill">{{ bookDetail.book.publication_year }}</span>
              @for (genre of bookDetail.book.genres; track genre) {
                <span class="pill genre">{{ genre }}</span>
              }
            </div>
            <p class="summary">{{ bookDetail.book.summary }}</p>
            
            <div class="availability-actions">
              <div class="availability-status" [class.available]="bookDetail.available_copies > 0">
                <mat-icon>{{ bookDetail.available_copies > 0 ? 'check_circle' : 'cancel' }}</mat-icon>
                <span>{{ bookDetail.available_copies }} of {{ bookDetail.total_copies }} copies available</span>
              </div>

              @if (bookDetail.available_copies === 0) {
                <div class="source-picker">
                  <label for="source-library">Source library</label>
                  @if (sourceLibrariesLoading) {
                    <p class="source-loading">Loading partner libraries...</p>
                  } @else {
                    <select
                      id="source-library"
                      class="source-select"
                      [value]="selectedSourceLibrary"
                      (change)="onSourceLibraryChange($event)"
                    >
                      @for (library of sourceLibraries; track library.code) {
                        <option [value]="library.code">{{ library.display_name }}</option>
                      }
                    </select>
                  }
                </div>

                <button
                  mat-flat-button
                  color="primary"
                  class="ill-request-btn"
                  (click)="requestILL()"
                  [disabled]="illLoading || sourceLibrariesLoading || !selectedSourceLibrary"
                >
                  <mat-icon>local_shipping</mat-icon>
                  {{ illLoading ? 'Requesting...' : 'Request from other libraries' }}
                </button>
              }
            </div>
          </div>
        </div>

        <div class="instances-section">
          <h2><mat-icon>dataset</mat-icon> Holdings</h2>
          <div class="instances-grid">
            @for (instance of bookDetail.instances; track instance.id) {
              <div class="instance-card" [attr.data-status]="instance.status">
                <div class="instance-header">
                  <span class="barcode">{{ instance.barcode }}</span>
                  <span class="status-badge">{{ instance.status }}</span>
                </div>
                <div class="instance-details">
                  <p><strong>Location:</strong> {{ instance.location }}</p>
                  <p><strong>Call Number:</strong> {{ instance.call_number }}</p>
                  <p><strong>Condition:</strong> {{ instance.condition }}</p>
                </div>
              </div>
            }
          </div>
        </div>
      }
    </div>
  `,
  styles: [`
    :host { display: block; height: 100%; overflow-y: auto; }
    .page-container { max-width: 960px; margin: 0 auto; padding: 32px 24px; }

    .back-link {
      display: inline-flex; align-items: center; gap: 4px;
      font-family: var(--font-serif); font-size: 0.9rem; font-weight: 600;
      color: var(--stone-500); text-decoration: none; margin-bottom: 32px;
      &:hover { color: var(--stone-800); }
    }

    .book-header {
      display: flex; gap: 32px; margin-bottom: 48px;
    }

    .book-cover-placeholder {
      width: 200px; height: 300px; background: var(--stone-200);
      display: flex; align-items: center; justify-content: center;
      border-radius: 8px; flex-shrink: 0;
      mat-icon { font-size: 64px; width: 64px; height: 64px; color: var(--stone-400); }
    }

    .book-info {
      h1 {
        font-family: var(--font-serif); font-size: 2.2rem; font-weight: 700;
        color: var(--stone-900); margin: 0 0 8px 0; line-height: 1.2;
      }
      .author {
        font-family: var(--font-sans); font-size: 1.1rem; color: var(--stone-600);
        margin: 0 0 24px 0;
      }
      .summary {
        font-family: var(--font-serif); font-size: 1rem; line-height: 1.6;
        color: var(--stone-800); margin-bottom: 32px;
      }
    }

    .meta-row {
      display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 24px;
      .pill {
        background: var(--stone-100); padding: 4px 12px; border-radius: 16px;
        font-size: 0.8rem; font-family: var(--font-mono); color: var(--stone-600);
        &.genre { background: var(--indigo-50); color: var(--indigo-700); }
      }
    }

    .availability-actions {
      display: flex; flex-direction: column; align-items: flex-start; gap: 16px;
    }

    .availability-status {
      display: flex; align-items: center; gap: 8px;
      padding: 12px 16px; background: var(--red-50); border-radius: 6px;
      color: var(--red-800); font-weight: 600;
      &.available { background: var(--emerald-50); color: var(--emerald-800); }
    }

    .ill-request-btn {
      background-color: var(--stone-800) !important;
      color: white !important;
    }

    .source-picker {
      display: flex;
      flex-direction: column;
      gap: 6px;

      label {
        font-size: 0.8rem;
        font-weight: 600;
        color: var(--stone-600);
      }
    }

    .source-select {
      min-width: 320px;
      padding: 8px 10px;
      border: 1px solid var(--stone-300);
      border-radius: 6px;
      background: white;
      font-size: 0.9rem;
      color: var(--stone-700);
    }

    .source-loading {
      margin: 0;
      font-size: 0.85rem;
      color: var(--stone-500);
      font-style: italic;
    }

    .instances-section {
      h2 {
        display: flex; align-items: center; gap: 10px;
        font-family: var(--font-serif); font-size: 1.4rem; color: var(--stone-800);
        margin-bottom: 24px;
        mat-icon { color: var(--stone-400); }
      }
    }

    .instances-grid {
      display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px;
    }

    .instance-card {
      background: white; border: 1px solid var(--stone-200); border-radius: 8px;
      padding: 16px;
      
      .instance-header {
        display: flex; justify-content: space-between; align-items: center;
        margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid var(--stone-100);
        .barcode { font-family: var(--font-mono); font-size: 0.8rem; color: var(--stone-400); }
      }

      .status-badge {
        font-size: 0.7rem; font-weight: 700; text-transform: uppercase;
        padding: 2px 8px; border-radius: 4px; background: var(--stone-100); color: var(--stone-600);
      }
      
      &[data-status="available"] .status-badge { background: var(--emerald-50); color: var(--emerald-700); }
      &[data-status="checked_out"] .status-badge { background: var(--amber-50); color: var(--amber-700); }
      &[data-status="missing"] .status-badge { background: var(--red-50); color: var(--red-700); }
      
      .instance-details p {
        margin: 4px 0; font-size: 0.9rem; color: var(--stone-700);
        strong { font-weight: 600; color: var(--stone-500); font-size: 0.8rem; }
      }
    }
  `]
})
export class BookDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private catalogService = inject(CatalogService);
  private illService = inject(ILLService);
  private userService = inject(UserService);
  private snackBar = inject(MatSnackBar);

  bookDetail: BookDetailResponse | null = null;
  loading = true;
  error: string | null = null;

  illLoading = false;
  sourceLibraries: ILLSourceLibrary[] = [];
  sourceLibrariesLoading = false;
  selectedSourceLibrary = '';

  ngOnInit() {
    const bookId = this.route.snapshot.paramMap.get('bookId');
    if (!bookId) {
      this.error = 'No book ID provided';
      this.loading = false;
      return;
    }

    this.catalogService.getBook(bookId).subscribe({
      next: (data) => {
        this.bookDetail = data;
        if (data.available_copies === 0) {
          this.loadSourceLibraries();
        }
        this.loading = false;
      },
      error: (err) => {
        this.error = 'Failed to load book details';
        this.loading = false;
      }
    });
  }

  requestILL() {
    if (!this.bookDetail) return;
    if (!this.selectedSourceLibrary) {
      this.snackBar.open('Please select a source library first.', 'Close', { duration: 4000 });
      return;
    }

    if (!confirm('This item is unavailable locally. Would you like to request it from another library in the network?')) {
      return;
    }

    const currentUser = this.userService.currentUser();

    this.illLoading = true;
    this.illService.createRequest({
      book_id: this.bookDetail.book.id,
      patron_id: currentUser.id,
      source_library: this.selectedSourceLibrary,
      isbn: this.bookDetail.book.isbn || undefined
    }).subscribe({
      next: (req) => {
        this.illLoading = false;
        this.snackBar.open('ILL Request placed successfully!', 'Close', { duration: 5000 });
      },
      error: (err) => {
        this.illLoading = false;
        console.error(err);
        this.snackBar.open('Failed to place request: ' + (err.error?.detail || err.message), 'Close', { duration: 5000 });
      }
    });
  }

  onSourceLibraryChange(event: Event): void {
    const target = event.target as HTMLSelectElement | null;
    this.selectedSourceLibrary = target?.value ?? '';
  }

  private loadSourceLibraries(): void {
    this.sourceLibrariesLoading = true;
    this.illService.listLendingLibraries().subscribe({
      next: (libraries) => {
        this.sourceLibraries = libraries;
        this.selectedSourceLibrary = libraries[0]?.code ?? '';
        this.sourceLibrariesLoading = false;
      },
      error: () => {
        this.sourceLibraries = [];
        this.selectedSourceLibrary = '';
        this.sourceLibrariesLoading = false;
      },
    });
  }
}
