
import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import {
    CatalogSearchResponse,
    BookDetailResponse,
    BookAvailabilityResponse
} from '../../shared/models/catalog.models';
import { getServiceHeaders, getServiceUrl } from '../config/app-config';

@Injectable({
    providedIn: 'root'
})
export class CatalogService {
    private readonly apiUrl = getServiceUrl('catalog');

    constructor(private http: HttpClient) { }


    searchBooks(
        query?: string,
        filters?: {
            isbn?: string;
            genre?: string;
            author?: string;
            stratum?: number;
            series?: string;
            available?: boolean;
        },
        pagination?: {
            limit?: number;
            offset?: number;
        }
    ): Observable<CatalogSearchResponse> {
        let params = new HttpParams();

        if (query) params = params.set('q', query);

        if (filters) {
            if (filters.isbn) params = params.set('isbn', filters.isbn);
            if (filters.genre) params = params.set('genre', filters.genre);
            if (filters.author) params = params.set('author', filters.author);
            if (filters.stratum) params = params.set('stratum', filters.stratum);
            if (filters.series) params = params.set('series', filters.series);
            if (filters.available !== undefined) params = params.set('available', filters.available);
        }

        if (pagination) {
            if (pagination.limit) params = params.set('limit', pagination.limit);
            if (pagination.offset) params = params.set('offset', pagination.offset);
        }

        return this.http.get<CatalogSearchResponse>(`${this.apiUrl}/books`, { params, headers: getServiceHeaders() });
    }

    getBook(bookId: string): Observable<BookDetailResponse> {
        return this.http.get<BookDetailResponse>(`${this.apiUrl}/books/${bookId}`, { headers: getServiceHeaders() });
    }

    getBookAvailability(bookId: string): Observable<BookAvailabilityResponse> {
        return this.http.get<BookAvailabilityResponse>(`${this.apiUrl}/books/${bookId}/availability`, { headers: getServiceHeaders() });
    }
}
