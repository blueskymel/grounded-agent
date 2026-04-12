import { Component, OnInit, ChangeDetectorRef } from '@angular/core'
import { CommonModule } from '@angular/common'
import { FormsModule } from '@angular/forms'
import { ApiService } from './api.service'
import { ChatResponse } from './api.types'

type DemoMessage = {
  role: 'user' | 'assistant'
  text: string
  citations?: Array<{ doc_id: string; score?: number }>
}

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
<div class="layout">
  <aside class="sidebar">

    <div *ngIf="apiStatus === 'down'" class="api-banner">
      API is not reachable. The demo cannot run until the backend is up.
    </div>

    <div class="chat-stack">

      <section class="chat-panel before-panel">
        <div class="panel-head">
          ❌ Before - AI fabricates an answer
        </div>

        <div class="messages">
          <div *ngFor="let m of beforeMessages" class="msg-row" [class.user-row]="m.role === 'user'">
            <div class="bubble" [class.user-bubble]="m.role === 'user'" [class.assistant-bubble]="m.role === 'assistant'">
              <div class="bubble-text">{{m.text}}</div>
              <div class="cite-list" *ngIf="m.citations?.length">
                <div *ngFor="let c of m.citations" class="cite-item">
                  <span class="cite-doc">Citation: {{c.doc_id}}</span>
                  <span class="cite-score">Confidence: {{formatConfidence(c.score)}}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="input-row">
          <input
            [(ngModel)]="beforeDraft"
            [disabled]="apiStatus === 'down' || beforeSending"
            placeholder="Ask the BEFORE endpoint..."
            (keydown.enter)="sendBefore()"
          />
          <button (click)="sendBefore()" [disabled]="apiStatus === 'down' || beforeSending">Send</button>
        </div>
      </section>

      <section class="chat-panel after-panel">
        <div class="panel-head">
          ✅ After - AI refuses to guess
        </div>

        <div class="messages">
          <div *ngFor="let m of afterMessages" class="msg-row" [class.user-row]="m.role === 'user'">
            <div class="bubble" [class.user-bubble]="m.role === 'user'" [class.assistant-bubble]="m.role === 'assistant'">
              <div class="bubble-text">{{m.text}}</div>
              <div class="cite-list" *ngIf="m.citations?.length">
                <div *ngFor="let c of m.citations" class="cite-item">
                  <span class="cite-doc">Citation: {{c.doc_id}}</span>
                  <span class="cite-score">Confidence: {{formatConfidence(c.score)}}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="input-row">
          <input
            [(ngModel)]="afterDraft"
            [disabled]="apiStatus === 'down' || afterSending"
            placeholder="Ask the AFTER endpoint..."
            (keydown.enter)="sendAfter()"
          />
          <button (click)="sendAfter()" [disabled]="apiStatus === 'down' || afterSending">Send</button>
        </div>
      </section>

    </div>
  </aside>

  <main class="main">
    <div class="explain">
      <h2>What is wrong before vs fixed after</h2>

      <section class="explain-card bad-card">
        <h3>Before: what is wrong</h3>
        <ul>
          <li>The model can invent confident statements not proven by runbooks.</li>
          <li>For high-risk questions like SLA, it does not force a refusal.</li>
          <li>This creates business risk because fake policy facts look authoritative.</li>
        </ul>
        <div class="evidence" *ngIf="beforeLastAnswer">
          <div class="evidence-label">Live evidence from BEFORE endpoint</div>
          <div class="evidence-text">{{beforeLastAnswer}}</div>
        </div>
      </section>

      <section class="explain-card good-card">
        <h3>After: what is fixed and how</h3>
        <ul>
          <li>Guardrails enforce grounded answers and refusal when evidence is missing.</li>
          <li>The safe path blocks unsupported SLA-style claims.</li>
          <li>The fix is implemented at the backend policy layer, not just prompt wording.</li>
        </ul>
        <div class="evidence" *ngIf="afterLastAnswer">
          <div class="evidence-label">Live evidence from AFTER endpoint</div>
          <div class="evidence-text">{{afterLastAnswer}}</div>
        </div>
      </section>

    </div>
  </main>
</div>
  `,
  styles: [`
.layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.sidebar {
  width: 56%;
  flex: 0 0 56%;
  border-right: 1px solid #e5e7eb;
  overflow: auto;
  padding: 14px;
  background: #f8fafc;
}

.main {
  width: 44%;
  flex: 1 1 auto;
  min-width: 0;
  overflow: auto;
  padding: 14px;
  background: #ffffff;
}

.api-banner {
  margin-bottom: 10px;
  background: #fff3cd;
  border: 1px solid #ffc107;
  border-radius: 8px;
  padding: 8px 10px;
  color: #7c5a00;
  font-size: 0.84rem;
}

.chat-stack {
  display: grid;
  grid-template-rows: 1fr 1fr;
  gap: 12px;
  height: calc(100vh - 46px);
}

.chat-panel {
  border: 1px solid #d1d5db;
  border-radius: 10px;
  background: #ffffff;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.panel-head {
  padding: 8px 10px;
  font-size: 0.88rem;
  font-weight: 700;
  border-bottom: 1px solid #e5e7eb;
}

.before-panel .panel-head {
  color: #b91c1c;
  background: #fef2f2;
}

.after-panel .panel-head {
  color: #166534;
  background: #f0fdf4;
}

.messages {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 10px;
}

.msg-row {
  display: flex;
  margin: 8px 0;
}

.user-row {
  justify-content: flex-end;
}

.bubble {
  max-width: 92%;
  border-radius: 10px;
  padding: 8px 10px;
}

.user-bubble {
  background: #dbeafe;
  color: #1e3a8a;
}

.assistant-bubble {
  background: #f3f4f6;
  color: #111827;
  border: 1px solid #e5e7eb;
}

.bubble-text {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
  line-height: 1.42;
  font-size: 0.83rem;
}

.cite-list {
  margin-top: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.cite-item {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  font-size: 0.72rem;
  color: #4b5563;
  background: #eef2f7;
  border-radius: 6px;
  padding: 4px 6px;
}

.cite-doc {
  font-weight: 600;
  overflow-wrap: anywhere;
}

.cite-score {
  color: #374151;
  white-space: nowrap;
}

.input-row {
  display: flex;
  gap: 8px;
  padding: 10px;
  border-top: 1px solid #e5e7eb;
}

.input-row input {
  flex: 1;
  min-width: 0;
  padding: 8px 9px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
}

.input-row button {
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: #f9fafb;
  cursor: pointer;
}

.input-row button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.explain h2 {
  margin: 0 0 10px;
  font-size: 1.05rem;
}

.explain-card {
  border-radius: 10px;
  padding: 10px 12px;
  margin-bottom: 10px;
}

.bad-card {
  border: 1px solid #fecaca;
  background: #fef2f2;
}

.good-card {
  border: 1px solid #bbf7d0;
  background: #f0fdf4;
}

.neutral-card {
  border: 1px solid #e5e7eb;
  background: #f9fafb;
}

.explain-card h3 {
  margin: 0 0 6px;
  font-size: 0.92rem;
}

.explain-card ul,
.explain-card ol {
  margin: 0;
  padding-left: 18px;
  font-size: 0.82rem;
  line-height: 1.45;
}

.evidence {
  margin-top: 8px;
  padding-top: 7px;
  border-top: 1px dashed rgba(0, 0, 0, 0.2);
}

.evidence-label {
  font-size: 0.74rem;
  font-weight: 700;
  margin-bottom: 4px;
}

.evidence-text {
  font-size: 0.78rem;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
}

@media (max-width: 980px) {
  .layout {
    flex-direction: column;
    height: auto;
    min-height: 100vh;
  }

  .sidebar,
  .main {
    width: 100%;
    flex: none;
  }

  .chat-stack {
    height: auto;
    grid-template-rows: auto auto;
  }

  .chat-panel {
    min-height: 300px;
  }
}
`]
})
export class AppComponent implements OnInit {
  apiStatus: 'checking' | 'up' | 'down' = 'checking'

  beforeDraft = ''
  afterDraft = ''

  beforeSending = false
  afterSending = false

  beforeMessages: DemoMessage[] = []
  afterMessages: DemoMessage[] = []

  beforeLastAnswer = ''
  afterLastAnswer = ''

  constructor(private api: ApiService, private cdr: ChangeDetectorRef) {}

  ngOnInit() {
    this.api.health().subscribe({
      next: () => {
        this.apiStatus = 'up'
        this.cdr.detectChanges()
      },
      error: () => {
        this.apiStatus = 'down'
        this.cdr.detectChanges()
      }
    })
  }

  sendBefore() {
    const msg = this.beforeDraft.trim()
    if (!msg || this.beforeSending || this.apiStatus === 'down') return

    this.beforeSending = true
    this.beforeDraft = ''
    this.beforeMessages = [...this.beforeMessages, { role: 'user', text: msg }]

    this.api.chatBefore(msg).subscribe({
      next: (res: ChatResponse) => {
        this.beforeMessages = [
          ...this.beforeMessages,
          {
            role: 'assistant',
            text: res.answer,
            citations: (res.citations ?? []).map(c => ({ doc_id: c.doc_id, score: c.score }))
          }
        ]
        this.beforeLastAnswer = res.answer
        this.beforeSending = false
        this.cdr.detectChanges()
      },
      error: () => {
        this.beforeMessages = [...this.beforeMessages, {
          role: 'assistant',
          text: 'Request failed for BEFORE endpoint.'
        }]
        this.beforeSending = false
        this.cdr.detectChanges()
      }
    })
  }

  sendAfter() {
    const msg = this.afterDraft.trim()
    if (!msg || this.afterSending || this.apiStatus === 'down') return

    this.afterSending = true
    this.afterDraft = ''
    this.afterMessages = [...this.afterMessages, { role: 'user', text: msg }]

    this.api.chatAfter(msg).subscribe({
      next: (res: ChatResponse) => {
        this.afterMessages = [
          ...this.afterMessages,
          {
            role: 'assistant',
            text: res.answer,
            citations: (res.citations ?? []).map(c => ({ doc_id: c.doc_id, score: c.score }))
          }
        ]
        this.afterLastAnswer = res.answer
        this.afterSending = false
        this.cdr.detectChanges()
      },
      error: () => {
        this.afterMessages = [...this.afterMessages, {
          role: 'assistant',
          text: 'Request failed for AFTER endpoint.'
        }]
        this.afterSending = false
        this.cdr.detectChanges()
      }
    })
  }

  formatConfidence(score?: number): string {
    if (score === undefined || score === null) return 'N/A'
    const pct = Math.max(0, Math.min(100, score * 100))
    return `${pct.toFixed(1)}%`
  }
}
