
import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { Router } from '@angular/router';

@Component({
    selector: 'app-home',
    standalone: true,
    imports: [CommonModule, RouterLink, MatIconModule, MatButtonModule, ReactiveFormsModule],
    template: `
    <div class="home-container">
      <section class="hero-section">
        <div class="hero-content">
          <h1>Welcome to the Pachyderm Archive</h1>
          <p>Explore our vast collection of ancient wisdom and modern chronicles.</p>
          
          <div class="search-box">
            <mat-icon>search</mat-icon>
            <input 
              type="text" 
              [formControl]="searchControl" 
              (keydown.enter)="onSearch()"
              placeholder="Search by title, author, or ISBN..."
            >
            <button mat-flat-button color="primary" (click)="onSearch()">Search</button>
          </div>
        </div>
      </section>

      <div class="content-grid">
        <section class="quick-actions">
          <h2>Quick Actions</h2>
          <div class="action-cards">
            <a routerLink="/catalog" class="action-card">
              <div class="icon-wrapper blue"><mat-icon>menu_book</mat-icon></div>
              <div class="text">
                <h3>Browse Catalog</h3>
                <p>Find books and resources</p>
              </div>
            </a>
            <a routerLink="/profile" class="action-card">
              <div class="icon-wrapper green"><mat-icon>account_circle</mat-icon></div>
              <div class="text">
                <h3>My Account</h3>
                <p>View checkouts & renewals</p>
              </div>
            </a>
            <a routerLink="/chat" class="action-card">
              <div class="icon-wrapper purple"><mat-icon>chat</mat-icon></div>
              <div class="text">
                <h3>Ask Librarian</h3>
                <p>Get AI-powered assistance</p>
              </div>
            </a>
          </div>
        </section>

        <section class="featured-section">
          <div class="section-header">
            <h2>Featured Collection</h2>
            <a routerLink="/catalog" class="view-all">View All</a>
          </div>
          
          <div class="book-row">
            <!-- Mock Featured Books -->
            <a routerLink="/catalog/book-001" class="featured-book">
              <div class="cover-placeholder"></div>
              <div class="book-info">
                <h4>The Ivory Throne</h4>
                <p>George R.R. Mammoth</p>
              </div>
            </a>
            <a routerLink="/catalog/book-002" class="featured-book">
              <div class="cover-placeholder"></div>
              <div class="book-info">
                <h4>Tusk and Sensibility</h4>
                <p>Jane Elephanten</p>
              </div>
            </a>
            <a routerLink="/catalog/book-003" class="featured-book">
              <div class="cover-placeholder"></div>
              <div class="book-info">
                <h4>Great Ex-pachyderms</h4>
                <p>Charles Trunkens</p>
              </div>
            </a>
            <a routerLink="/catalog/book-004" class="featured-book">
              <div class="cover-placeholder"></div>
              <div class="book-info">
                <h4>The Fall of Lorde Tuskar</h4>
                <p>Lord Bertram Greytusk</p>
              </div>
            </a>
          </div>
        </section>
      </div>
    </div>
  `,
    styles: [`
    :host { display: block; height: 100%; overflow-y: auto; }

    .hero-section {
      background: linear-gradient(135deg, var(--primary-dark, #3730a3) 0%, var(--primary, #4f46e5) 100%);
      color: white; padding: 64px 32px; text-align: center;
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      margin-bottom: 48px;
    }

    .hero-content {
      max-width: 700px; width: 100%;
      h1 { font-family: var(--font-serif); font-size: 2.5rem; font-weight: 700; margin: 0 0 16px 0; }
      p { font-size: 1.1rem; opacity: 0.9; margin: 0 0 32px 0; font-weight: 300; }
    }

    .search-box {
      background: white; border-radius: 12px; padding: 8px;
      display: flex; align-items: center; gap: 12px;
      box-shadow: 0 8px 24px rgba(0,0,0,0.15); width: 100%; position: relative;
      
      mat-icon { margin-left: 12px; color: var(--stone-400); }
      
      input {
        border: none; background: transparent; flex: 1; font-size: 1rem;
        padding: 8px 0; outline: none; color: var(--stone-800);
        &::placeholder { color: var(--stone-400); }
      }

      button {
        border-radius: 8px; height: 40px; padding: 0 24px;
        background: var(--primary, #4f46e5); color: white; border: none; font-weight: 600; cursor: pointer;
        &:hover { background: var(--primary-dark, #4338ca); }
      }
    }

    .content-grid {
      max-width: 1100px; margin: 0 auto; padding: 0 32px 64px 32px;
      display: grid; gap: 48px;
    }

    .quick-actions h2, .featured-section h2 {
      font-family: var(--font-serif); font-size: 1.4rem; color: var(--stone-800); margin: 0 0 24px 0;
    }

    .action-cards {
      display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 24px;
    }

    .action-card {
      background: white; border: 1px solid var(--stone-200); border-radius: 12px; padding: 24px;
      display: flex; align-items: center; gap: 20px; text-decoration: none;
      transition: all 0.2s ease; cursor: pointer;

      &:hover {
        transform: translateY(-4px); box-shadow: 0 12px 24px rgba(0,0,0,0.06);
        border-color: var(--stone-300);
      }

      .icon-wrapper {
        width: 56px; height: 56px; border-radius: 12px; display: flex; align-items: center; justify-content: center;
        mat-icon { font-size: 28px; width: 28px; height: 28px; }
        &.blue { background: var(--blue-50); color: var(--blue-600); }
        &.green { background: var(--emerald-50); color: var(--emerald-600); }
        &.purple { background: var(--purple-50); color: var(--purple-600); }
      }

      .text {
        h3 { margin: 0 0 4px 0; font-size: 1.1rem; font-weight: 600; color: var(--stone-800); }
        p { margin: 0; font-size: 0.9rem; color: var(--stone-500); }
      }
    }

    .section-header { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 24px; }
    .view-all { font-size: 0.9rem; font-weight: 600; color: var(--primary, #4f46e5); text-decoration: none; }

    .book-row {
      display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 24px;
    }

    .featured-book {
      text-decoration: none; color: inherit; transition: transform 0.2s;
      &:hover { transform: translateY(-4px); }
      
      .cover-placeholder {
        height: 280px; background: var(--stone-200); border-radius: 8px; margin-bottom: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
      }
      
      .book-info {
        h4 { margin: 0 0 4px 0; font-family: var(--font-serif); font-size: 1rem; color: var(--stone-800); line-height: 1.3; }
        p { margin: 0; font-size: 0.85rem; color: var(--stone-500); }
      }
    }
  `]
})
export class HomeComponent {
    searchControl = new FormControl('');

    constructor(private router: Router) { }

    onSearch() {
        const query = this.searchControl.value;
        if (query && query.trim()) {
            this.router.navigate(['/catalog'], { queryParams: { q: query } });
        } else {
            this.router.navigate(['/catalog']);
        }
    }
}
