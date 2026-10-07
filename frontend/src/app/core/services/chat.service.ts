import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, BehaviorSubject } from 'rxjs';
import { tap } from 'rxjs/operators';
import { getServiceHeaders, getServiceUrl } from '../config/app-config';
import { UserService } from './user.service';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export interface ChatRequest {
  message: string;
  session_id?: string;
  active_patron?: {
    id: string;
    name?: string;
    role?: 'patron' | 'staff';
  };
}

export interface ChatResponse {
  response: string;
  session_id: string;
  bound_patron_id?: string | null;
  session_rebound?: boolean;
}

@Injectable({
  providedIn: 'root'
})
export class ChatService {
  private readonly apiUrl = getServiceUrl('agents');
  private sessionId: string | null = null;

  private messagesSubject = new BehaviorSubject<ChatMessage[]>([]);
  messages$ = this.messagesSubject.asObservable();

  private loadingSubject = new BehaviorSubject<boolean>(false);
  loading$ = this.loadingSubject.asObservable();

  constructor(
    private http: HttpClient,
    private userService: UserService,
  ) { }

  sendMessage(message: string): Observable<ChatResponse> {
    this.loadingSubject.next(true);

    // Add user message immediately
    const userMessage: ChatMessage = {
      role: 'user',
      content: message,
      timestamp: new Date()
    };
    this.addMessage(userMessage);

    const request: ChatRequest = {
      message,
      session_id: this.sessionId || undefined,
      active_patron: {
        id: this.userService.currentUser().id,
        name: this.userService.currentUser().name,
        role: this.userService.currentUser().role,
      },
    };

    return this.http.post<ChatResponse>(`${this.apiUrl}/chat`, request, { headers: getServiceHeaders() }).pipe(
      tap({
        next: (response) => {
          this.sessionId = response.session_id;

          // Add assistant message
          const assistantMessage: ChatMessage = {
            role: 'assistant',
            content: response.response,
            timestamp: new Date()
          };
          this.addMessage(assistantMessage);
          this.loadingSubject.next(false);
        },
        error: () => {
          // Add error message
          const errorMessage: ChatMessage = {
            role: 'assistant',
            content: 'Sorry, I encountered an error. Please try again.',
            timestamp: new Date()
          };
          this.addMessage(errorMessage);
          this.loadingSubject.next(false);
        }
      })
    );
  }

  private addMessage(message: ChatMessage): void {
    const currentMessages = this.messagesSubject.value;
    this.messagesSubject.next([...currentMessages, message]);
  }

  clearChat(): void {
    this.messagesSubject.next([]);
    this.sessionId = null;
  }

  rotateSession(): void {
    this.sessionId = null;
  }

  getSessionId(): string | null {
    return this.sessionId;
  }
}
