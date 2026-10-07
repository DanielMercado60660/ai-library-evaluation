
import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';
import { debounceTime, distinctUntilChanged, takeUntil } from 'rxjs/operators';
import { Subject } from 'rxjs';

import { CatalogService } from '../../core/services/catalog.service';
import { BookWithAvailability } from '../../shared/models/catalog.models';

@Component({
    selector: 'app-book-list',
    standalone: true,
    imports: [CommonModule, ReactiveFormsModule, RouterLink, MatIconModule],
    template: `
    <div class="page-container">
      <div class="catalog-header">
        <h1><mat-icon>library_books</mat-icon> Library Catalog</h1>
        <div class="search-bar">
          <mat-icon class="search-icon">search</mat-icon>
          <input 
            type="text" 
            [formControl]="searchControl" 
            placeholder="Search by title, author, or ISBN..."
            class="search-input"
          >
        </div>
      </div>

      @if (loading) {
        <div class="loading-state">
          <p>Searching catalog...</p>
        </div>
      } @else if (error) {
        <div class="error-state">
          <mat-icon>error_outline</mat-icon>
          <p>{{ error }}</p>
        </div>
      } @else if (books.length === 0) {
        <div class="empty-state">
          <mat-icon>menu_book</mat-icon>
          <p>No books found matching your query.</p>
        </div>
      } @else {
        <div class="book-grid">
          @for (book of books; track book.id) {
            <a [routerLink]="['/catalog', book.id]" class="book-card">
              <div class="book-cover-placeholder">
                <mat-icon>book</mat-icon>
              </div>
              <div class="book-info">
                <h3 class="book-title">{{ book.title }}</h3>
                <p class="book-author">{{ book.author }}</p>
                <div class="book-meta">
                  <span class="year">{{ book.publication_year }}</span>
                  <span class="availability" [class.available]="book.available_copies > 0">
                    {{ book.available_copies }} / {{ book.total_copies }} available
                  </span>
                </div>
              </div>
            </a>
          }
        </div>
      }
    </div>
  `,
    styles: [`
    :host { display: block; height: 100%; overflow-y: auto; }
    .page-container { max-width: 1200px; margin: 0 auto; padding: 32px 24px; }

    .catalog-header {
      margin-bottom: 32px;
      h1 {
        display: flex; align-items: center; gap: 10px;
        font-family: var(--font-serif); font-size: 1.8rem; font-weight: 700;
        color: var(--stone-800); margin: 0 0 24px 0;
        mat-icon { font-size: 32px; width: 32px; height: 32px; color: var(--stone-500); }
      }
    }

    .search-bar {
      position: relative; max-width: 600px;
      .search-icon {
        position: absolute; left: 16px; top: 50%; transform: translateY(-50%);
        color: var(--stone-400); pointer-events: none;
      }
      .search-input {
        width: 100%; padding: 12px 16px 12px 48px;
        border: 1px solid var(--stone-300); border-radius: 8px;
        font-family: var(--font-sans); font-size: 1rem;
        transition: all 0.2s;
        &:focus {
          outline: none; border-color: var(--stone-500);
          box-shadow: 0 0 0 3px var(--stone-100);
        }
      }
    }

    .loading-state, .error-state, .empty-state {
      text-align: center; padding: 60px 20px; color: var(--stone-400);
      mat-icon { font-size: 48px; width: 48px; height: 48px; margin-bottom: 16px; opacity: 0.5; }
      p { margin: 0; font-family: var(--font-serif); font-size: 1.1rem; }
    }
    .error-state { color: var(--red-800); mat-icon { opacity: 1; } }

    .book-grid {
      display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 24px;
    }

    .book-card {
      display: flex; flex-direction: column;
      background: white; border: 1px solid var(--stone-200); border-radius: 8px;
      overflow: hidden; text-decoration: none; color: inherit;
      transition: all 0.2s ease;
      &:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        border-color: var(--stone-300);
      }
    }

    .book-cover-placeholder {
      height: 160px; background: var(--stone-100);
      display: flex; align-items: center; justify-content: center;
      mat-icon { font-size: 48px; width: 48px; height: 48px; color: var(--stone-300); }
    }

    .book-info { padding: 16px; flex: 1; display: flex; flex-direction: column; }
    
    .book-title {
      font-family: var(--font-serif); font-size: 1.1rem; font-weight: 600;
      color: var(--stone-800); margin: 0 0 4px 0; line-height: 1.4;
    }
    
    .book-author {
      font-family: var(--font-sans); font-size: 0.9rem; color: var(--stone-500);
      margin: 0 0 12px 0;
    }

    .book-meta {
      margin-top: auto; display: flex; justify-content: space-between; align-items: center;
      font-size: 0.8rem; font-family: var(--font-mono); color: var(--stone-400);
      
      .availability {
        font-weight: 600;
        &.available { color: var(--emerald-600); }
      }
    }
  `]
})
export class BookListComponent implements OnInit, OnDestroy {
    searchControl = new FormControl('');
    books: BookWithAvailability[] = [];
    loading = false;
    error: string | null = null;
    private destroy$ = new Subject<void>();

    constructor(
        private catalogService: CatalogService,
        private route: ActivatedRoute,
    ) { }

    ngOnInit() {
        this.setupSearch();
        this.route.queryParamMap.pipe(takeUntil(this.destroy$)).subscribe(params => {
            const query = (params.get('q') || '').trim();
            this.searchControl.setValue(query, { emitEvent: false });
            this.performSearch(query);
        });
    }

    ngOnDestroy() {
        this.destroy$.next();
        this.destroy$.complete();
    }

    private setupSearch() {
        this.searchControl.valueChanges.pipe(
            debounceTime(300),
            distinctUntilChanged(),
            takeUntil(this.destroy$),
        ).subscribe(query => {
            this.performSearch((query || '').trim());
        });
    }

    private performSearch(query: string) {
        this.loading = true;
        this.error = null;
        this.catalogService.searchBooks(query).subscribe({
            next: (response) => {
                this.books = response.books;
                this.loading = false;
            },
            error: () => {
                this.error = 'Failed to load books. Please try again later.';
                this.loading = false;
            }
        });
    }
}
