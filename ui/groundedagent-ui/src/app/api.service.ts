import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ChatResponse, HealthResponse } from './api.types';

@Injectable({ providedIn: 'root' })
export class ApiService {

  constructor(private http: HttpClient) {}

  health(): Observable<HealthResponse> {
    return this.http.get<HealthResponse>('/api/health');
  }

  chat(message: string): Observable<ChatResponse> {
    return this.http.post<ChatResponse>('/api/chat', { message });
  }

}