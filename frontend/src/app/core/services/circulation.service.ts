
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import {
    Patron,
    PatronResponse,
    PatronSummaryResponse,
    RenewalResponse
} from '../../shared/models/circulation.models';
import { getServiceHeaders, getServiceUrl } from '../config/app-config';

@Injectable({
    providedIn: 'root'
})
export class CirculationService {
    private readonly apiUrl = getServiceUrl('circulation');

    constructor(private http: HttpClient) { }

    getPatrons(): Observable<Patron[]> {
        return this.http.get<Patron[]>(`${this.apiUrl}/patrons`, { headers: getServiceHeaders() });
    }

    getPatron(patronId: string): Observable<PatronResponse> {
        return this.http.get<PatronResponse>(`${this.apiUrl}/patrons/${patronId}`, { headers: getServiceHeaders() });
    }

    getPatronSummary(patronId: string): Observable<PatronSummaryResponse> {
        return this.http.get<PatronSummaryResponse>(`${this.apiUrl}/patrons/${patronId}/summary`, { headers: getServiceHeaders() });
    }

    renewCheckout(checkoutId: string): Observable<RenewalResponse> {
        return this.http.post<RenewalResponse>(`${this.apiUrl}/checkouts/${checkoutId}/renew`, {}, { headers: getServiceHeaders() });
    }
}
