import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { signal } from '@angular/core';

import { ChatService, ChatResponse } from './chat.service';
import { UserService, UserIdentity } from './user.service';

describe('ChatService', () => {
  let service: ChatService;
  let httpMock: HttpTestingController;

  const mockUser: UserIdentity = {
    id: 'patron-001',
    name: 'Trunsworth Greyvale',
    role: 'patron',
    avatarInitials: 'TG',
  };

  beforeEach(() => {
    const userServiceMock = {
      currentUser: signal(mockUser).asReadonly(),
    };

    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [
        ChatService,
        { provide: UserService, useValue: userServiceMock },
      ],
    });

    service = TestBed.inject(ChatService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('should POST to /chat on sendMessage', () => {
    const response: ChatResponse = {
      response: 'Found a book for you.',
      session_id: 'sess-001',
    };

    service.sendMessage('Find me a book').subscribe();

    const req = httpMock.expectOne((r) => r.url.endsWith('/chat'));
    expect(req.request.method).toBe('POST');
    expect(req.request.body.message).toBe('Find me a book');
    expect(req.request.body.active_patron.id).toBe('patron-001');
    req.flush(response);
  });

  it('should add user and assistant messages to messages$', () => {
    const response: ChatResponse = {
      response: 'Here is your book.',
      session_id: 'sess-001',
    };

    let messages: unknown[] = [];
    service.messages$.subscribe((m) => (messages = m));

    service.sendMessage('Hello').subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/chat'));
    req.flush(response);

    expect(messages.length).toBe(2);
    expect((messages[0] as any).role).toBe('user');
    expect((messages[0] as any).content).toBe('Hello');
    expect((messages[1] as any).role).toBe('assistant');
    expect((messages[1] as any).content).toBe('Here is your book.');
  });

  it('should set sessionId from response', () => {
    const response: ChatResponse = {
      response: 'Done.',
      session_id: 'sess-abc',
    };

    expect(service.getSessionId()).toBeNull();

    service.sendMessage('Hi').subscribe();
    httpMock.expectOne((r) => r.url.endsWith('/chat')).flush(response);

    expect(service.getSessionId()).toBe('sess-abc');
  });

  it('should include session_id in subsequent requests', () => {
    const response: ChatResponse = {
      response: 'Done.',
      session_id: 'sess-abc',
    };

    service.sendMessage('First').subscribe();
    httpMock.expectOne((r) => r.url.endsWith('/chat')).flush(response);

    service.sendMessage('Second').subscribe();
    const req = httpMock.expectOne((r) => r.url.endsWith('/chat'));
    expect(req.request.body.session_id).toBe('sess-abc');
    req.flush(response);
  });

  it('should add error message on HTTP failure', () => {
    let messages: unknown[] = [];
    service.messages$.subscribe((m) => (messages = m));

    service.sendMessage('Fail').subscribe({ error: () => {} });
    const req = httpMock.expectOne((r) => r.url.endsWith('/chat'));
    req.error(new ProgressEvent('error'));

    expect(messages.length).toBe(2);
    expect((messages[1] as any).role).toBe('assistant');
    expect((messages[1] as any).content).toContain('error');
  });

  it('should set loading to false after response', () => {
    let loading = true;
    service.loading$.subscribe((l) => (loading = l));

    service.sendMessage('Test').subscribe();
    expect(loading).toBeTrue();

    const req = httpMock.expectOne((r) => r.url.endsWith('/chat'));
    req.flush({ response: 'OK', session_id: 's1' });
    expect(loading).toBeFalse();
  });

  it('should clear messages and sessionId on clearChat', () => {
    const response: ChatResponse = {
      response: 'Done.',
      session_id: 'sess-abc',
    };
    service.sendMessage('Hi').subscribe();
    httpMock.expectOne((r) => r.url.endsWith('/chat')).flush(response);

    service.clearChat();

    let messages: unknown[] = [];
    service.messages$.subscribe((m) => (messages = m));
    expect(messages.length).toBe(0);
    expect(service.getSessionId()).toBeNull();
  });

  it('should clear sessionId on rotateSession', () => {
    const response: ChatResponse = {
      response: 'Done.',
      session_id: 'sess-abc',
    };
    service.sendMessage('Hi').subscribe();
    httpMock.expectOne((r) => r.url.endsWith('/chat')).flush(response);

    service.rotateSession();
    expect(service.getSessionId()).toBeNull();
  });
});
