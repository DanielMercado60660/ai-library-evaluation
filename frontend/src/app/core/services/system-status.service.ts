import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, forkJoin, of } from 'rxjs';
import { catchError, map } from 'rxjs/operators';
import { UserService } from './user.service';
import { getServiceHeaders, getServiceUrl } from '../config/app-config';
import { CatalogSearchResponse } from '../../shared/models/catalog.models';

export interface ServiceHealthStatus {
  id: string;
  label: string;
  baseUrl: string;
  healthy: boolean;
  statusCode: number | null;
  latencyMs: number | null;
  detail: string;
  checkedAt: Date;
}

export interface SmokeCheckResult {
  id: 'catalog' | 'circulation' | 'ill';
  title: string;
  success: boolean;
  detail: string;
  timestamp: Date;
}

interface ServiceEndpoint {
  id: string;
  label: string;
  baseUrl: string;
}
interface PatronSummaryResponse {
  patron: { id: string };
  checkouts: unknown[];
  holds: unknown[];
}

interface InboundQueryResponse {
  held: boolean;
  available_copies: number;
  loanable: boolean;
}


const SERVICE_ENDPOINTS: readonly ServiceEndpoint[] = [
  { id: 'agents', label: 'Agents API', baseUrl: getServiceUrl('agents') },
  { id: 'catalog', label: 'Catalog', baseUrl: getServiceUrl('catalog') },
  { id: 'circulation', label: 'Circulation', baseUrl: getServiceUrl('circulation') },
  { id: 'ill', label: 'ILL', baseUrl: getServiceUrl('ill') },
  { id: 'registry', label: 'Registry', baseUrl: getServiceUrl('registry') },
];

@Injectable({
  providedIn: 'root',
})
export class SystemStatusService {
  constructor(
    private readonly http: HttpClient,
    private readonly userService: UserService,
  ) { }

  checkAllServices(): Observable<ServiceHealthStatus[]> {
    return forkJoin(SERVICE_ENDPOINTS.map((endpoint) => this.checkService(endpoint)));
  }

  runCatalogSmokeCheck(): Observable<SmokeCheckResult> {
    return this.http
      .get<CatalogSearchResponse>(`${getServiceUrl('catalog')}/books`, {
        params: { q: 'greyhorn', limit: '3' },
        headers: getServiceHeaders(),
      })
      .pipe(
        map((response) => {
          const topTitle = response.books[0]?.title ?? 'none';
          return {
            id: 'catalog' as const,
            title: 'Catalog search',
            success: response.total > 0,
            detail: `Found ${response.total} result(s); top title: ${topTitle}`,
            timestamp: new Date(),
          };
        }),
        catchError((error: HttpErrorResponse) =>
          of({
            id: 'catalog' as const,
            title: 'Catalog search',
            success: false,
            detail: this.describeHttpError(error),
            timestamp: new Date(),
          }),
        ),
      );
  }

  runCirculationSmokeCheck(): Observable<SmokeCheckResult> {
    const patronId = this.userService.currentUser().id;
    return this.http.get<PatronSummaryResponse>(`${getServiceUrl('circulation')}/patrons/${patronId}/summary`, {
      headers: getServiceHeaders(),
    }).pipe(
      map((response) => ({
        id: 'circulation' as const,
        title: 'Patron summary',
        success: true,
        detail: `Patron ${response.patron.id} loaded; checkouts=${response.checkouts.length}, holds=${response.holds.length}`,
        timestamp: new Date(),
      })),
      catchError((error: HttpErrorResponse) =>
        of({
          id: 'circulation' as const,
          title: 'Patron summary',
          success: false,
          detail: this.describeHttpError(error),
          timestamp: new Date(),
        }),
      ),
    );
  }

  runIllSmokeCheck(): Observable<SmokeCheckResult> {
    return this.http
      .post<InboundQueryResponse>(`${getServiceUrl('ill')}/inbound/query`, {
        isbn: '978-0-HANNO-0001',
      }, { headers: getServiceHeaders() })
      .pipe(
        map((response) => ({
          id: 'ill' as const,
          title: 'Inbound holdings query',
          success: response.held,
          detail: `held=${response.held}, available=${response.available_copies}, loanable=${response.loanable}`,
          timestamp: new Date(),
        })),
        catchError((error: HttpErrorResponse) =>
          of({
            id: 'ill' as const,
            title: 'Inbound holdings query',
            success: false,
            detail: this.describeHttpError(error),
            timestamp: new Date(),
          }),
        ),
      );
  }

  private checkService(endpoint: ServiceEndpoint): Observable<ServiceHealthStatus> {
    const startedAt = performance.now();
    return this.http
      .get<{ service?: string; status?: string; version?: string }>(`${endpoint.baseUrl}/health`, {
        observe: 'response',
        headers: getServiceHeaders(),
      })
      .pipe(
        map((response) => {
          const elapsed = Math.round(performance.now() - startedAt);
          const service = response.body?.service ?? endpoint.id;
          const status = response.body?.status ?? 'ok';
          const version = response.body?.version ? `v${response.body.version}` : '';
          return {
            id: endpoint.id,
            label: endpoint.label,
            baseUrl: endpoint.baseUrl,
            healthy: response.ok,
            statusCode: response.status,
            latencyMs: elapsed,
            detail: `${service}: ${status}${version ? ` (${version})` : ''}`,
            checkedAt: new Date(),
          };
        }),
        catchError((error: HttpErrorResponse) =>
          of({
            id: endpoint.id,
            label: endpoint.label,
            baseUrl: endpoint.baseUrl,
            healthy: false,
            statusCode: error.status || null,
            latencyMs: null,
            detail: this.describeHttpError(error),
            checkedAt: new Date(),
          }),
        ),
      );
  }

  private describeHttpError(error: HttpErrorResponse): string {
    if (error.status === 0) {
      return 'Service unreachable';
    }
    if (error.error?.detail && typeof error.error.detail === 'string') {
      return `${error.status}: ${error.error.detail}`;
    }
    return `${error.status}: ${error.message}`;
  }
}
