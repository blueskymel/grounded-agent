import { Injectable } from '@angular/core';
import { HttpClient, HttpResponse } from '@angular/common/http';
import { map, Observable, timeout } from 'rxjs';
import { ChatResponse, HealthResponse } from './api.types';

export type ChatResult = {
  data: ChatResponse;
  requestId?: string;
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly requestTimeoutMs = 12000;

  private base = typeof window !== 'undefined' && window.location.hostname !== 'localhost'
    ? 'https://grounded-agent-api.orangewave-2d52a1ea.eastus2.azurecontainerapps.io'
    : '/api';

  constructor(private http: HttpClient) {}

  health(): Observable<HealthResponse> {
    return this.http.get<HealthResponse>(`${this.base}/health`).pipe(timeout(5000));
  }

  chat(message: string): Observable<ChatResponse> {
    return this.http.post<ChatResponse>(`${this.base}/chat`, { message });
  }

  chatBefore(message: string): Observable<ChatResult> {
    return this.http.post<ChatResponse>(`${this.base}/chat/before`, { message }, { observe: 'response' }).pipe(
      timeout(this.requestTimeoutMs),
      map((res: HttpResponse<ChatResponse>) => ({
        data: res.body as ChatResponse,
        requestId: res.headers.get('x-request-id') ?? undefined,
      }))
    );
  }

  chatAfter(message: string): Observable<ChatResult> {
    return this.http.post<ChatResponse>(`${this.base}/chat/after`, { message }, { observe: 'response' }).pipe(
      timeout(this.requestTimeoutMs),
      map((res: HttpResponse<ChatResponse>) => ({
        data: res.body as ChatResponse,
        requestId: res.headers.get('x-request-id') ?? undefined,
      }))
    );
  }

  streamChat(
    message: string,
    onToken: (token: string) => void,
    onDone: () => void,
    onError?: (err: unknown) => void
  ): void {
    fetch(`${this.base}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ message }),
    })
      .then(async (response) => {
        if (!response.ok || !response.body) {
          throw new Error(`Streaming request failed: ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          const parts = buffer.split('\n\n');
          buffer = parts.pop() ?? '';

          for (const part of parts) {
            const line = part.trim();
            if (!line.startsWith('data:')) continue;

            const payload = line.slice(5).trim();
            if (!payload) continue;

            const evt = JSON.parse(payload);

            if (evt.type === 'token') {
              onToken(evt.value);
            } else if (evt.type === 'done') {
              onDone();
              return;
            } else if (evt.type === 'error') {
              throw new Error(evt.message || 'Stream error');
            }
          }
        }

        onDone();
      })
      .catch((err) => {
        if (onError) onError(err);
      });
  }
}