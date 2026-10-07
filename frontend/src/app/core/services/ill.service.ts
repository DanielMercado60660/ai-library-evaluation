import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { catchError, map } from 'rxjs/operators';
import { of } from 'rxjs';
import { getServiceHeaders, getServiceUrl } from '../config/app-config';

export interface ILLRequest {
    id: string;
    book_id: string;
    book_title: string;
    patron_id: string;
    status: string;
    requested_at: string;
    shipped_at?: string;
    received_at?: string;
    due_date?: string;
    returned_to_lender_at?: string;
    denial_reason?: string;
}

export interface ILLRequestCreate {
    book_id: string;
    patron_id: string;
    source_library: string;
    priority?: string;
    patron_justification?: string;
    isbn?: string;
}

export interface ILLSourceLibrary {
    code: string;
    display_name: string;
}

interface RegistryLibraryResponse {
    code: string;
    display_name: string;
    status: string;
    lending_enabled: boolean;
}

const FALLBACK_SOURCE_LIBRARIES: ILLSourceLibrary[] = [
    { code: 'mastodon-institute', display_name: 'Mastodon Institute of Technology' },
    { code: 'mammoth-valley', display_name: 'Mammoth Valley Public Library' },
    { code: 'ivory-university', display_name: 'Ivory University' },
    { code: 'tusk-conservatory', display_name: 'Tusk Conservatory' },
];

@Injectable({
    providedIn: 'root'
})
export class ILLService {
    private readonly apiUrl = getServiceUrl('ill');
    private readonly registryUrl = getServiceUrl('registry');

    constructor(private http: HttpClient) { }

    createRequest(request: ILLRequestCreate): Observable<ILLRequest> {
        return this.http.post<ILLRequest>(`${this.apiUrl}/requests`, request, { headers: getServiceHeaders() });
    }

    getRequests(patronId?: string): Observable<ILLRequest[]> {
        const params: any = {};
        if (patronId) params.patron_id = patronId;
        return this.http.get<ILLRequest[]>(`${this.apiUrl}/requests`, { headers: getServiceHeaders(), params });
    }

    listLendingLibraries(): Observable<ILLSourceLibrary[]> {
        return this.http
                .get<RegistryLibraryResponse[]>(`${this.registryUrl}/libraries`, {
                headers: getServiceHeaders(),
                params: { status: 'active', lending_enabled: true },
            })
            .pipe(
                map((libraries) =>
                    libraries
                        .filter((library) => library.code !== 'hanno-memorial')
                        .map((library) => ({ code: library.code, display_name: library.display_name })),
                ),
                map((libraries) => (libraries.length > 0 ? libraries : FALLBACK_SOURCE_LIBRARIES)),
                catchError(() => of(FALLBACK_SOURCE_LIBRARIES)),
            );
    }
}
