import { Routes } from '@angular/router';
import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { UserService } from './core/services/user.service';

const staffOnlyGuard: CanActivateFn = (_route, state) => {
  const userService = inject(UserService);
  const router = inject(Router);
  return userService.isStaff()
    ? true
    : router.createUrlTree(['/access-denied'], {
      queryParams: {
        reason: 'staff_only',
        from: state.url,
      },
    });
};

export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./core/layout/main-layout.component').then((m) => m.MainLayoutComponent),
    children: [
      { path: 'home', loadComponent: () => import('./features/home/home.component').then((m) => m.HomeComponent) },
      { path: 'chat', loadComponent: () => import('./features/chat-page/chat-page.component').then((m) => m.ChatPageComponent) },
      { path: 'runs', loadComponent: () => import('./features/runs/run-list.component').then((m) => m.RunListComponent) },
      { path: 'analytics', loadComponent: () => import('./features/analytics/analytics.component').then((m) => m.AnalyticsComponent) },
      { path: 'runs/:runId', loadComponent: () => import('./features/run-detail/run-detail.component').then((m) => m.RunDetailComponent) },
      { path: 'reports/:runId', loadComponent: () => import('./features/reports/report-view.component').then((m) => m.ReportViewComponent) },
      { path: 'replay/:runId', loadComponent: () => import('./features/replay/replay-view.component').then((m) => m.ReplayViewComponent) },
      { path: 'catalog', loadComponent: () => import('./features/catalog/book-list.component').then((m) => m.BookListComponent) },
      { path: 'catalog/:bookId', loadComponent: () => import('./features/catalog/book-detail.component').then((m) => m.BookDetailComponent) },
      { path: 'patrons', loadComponent: () => import('./features/patrons/patron-list.component').then((m) => m.PatronListComponent), canActivate: [staffOnlyGuard] },
      { path: 'profile', loadComponent: () => import('./features/profile/patron-profile.component').then((m) => m.PatronProfileComponent) },
      { path: 'profile/:id', loadComponent: () => import('./features/profile/patron-profile.component').then((m) => m.PatronProfileComponent) },
      { path: 'access-denied', loadComponent: () => import('./features/access-denied/access-denied.component').then((m) => m.AccessDeniedComponent) },
      { path: '', redirectTo: 'home', pathMatch: 'full' },
    ]
  },
  { path: '**', redirectTo: 'home' },
];
