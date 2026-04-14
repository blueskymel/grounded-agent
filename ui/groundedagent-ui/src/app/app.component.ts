import { Component, OnInit, ChangeDetectorRef } from '@angular/core'
import { CommonModule } from '@angular/common'
import { FormsModule } from '@angular/forms'
import { ApiService, ChatResult } from './api.service'
import { ChatResponse } from './api.types'

type DemoMessage = {
  role: 'user' | 'assistant'
  text: string
  citations?: Array<{ doc_id: string; score?: number }>
  trace?: ObsTrace
}

type ObsTrace = {
  endpoint: 'before' | 'after'
  requestId?: string
  question: string
  answer: string
  retrievalBackend: string
  timings?: ChatResponse['timings']
  citations: ChatResponse['citations']
  retrievedChunks: ChatResponse['retrieved_chunks']
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
              <button *ngIf="m.role === 'assistant' && m.trace" class="trace-link" (click)="openTrace(m.trace)">
                Behind the scenes
              </button>
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
              <button *ngIf="m.role === 'assistant' && m.trace" class="trace-link" (click)="openTrace(m.trace)">
                Behind the scenes
              </button>
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
          <li>For high-risk policy questions, it does not reliably force a refusal.</li>
          <li>This creates business risk because fake policy facts look authoritative.</li>
        </ul>
      </section>

      <section class="explain-card good-card">
        <h3>After: what is fixed and how</h3>
        <ul>
          <li>Guardrails enforce grounded answers and refusal when evidence is missing.</li>
          <li>The safe path blocks unsupported policy claims, not just one policy type.</li>
          <li>The fix is implemented at the backend policy layer, not just prompt wording.</li>
        </ul>
        <div class="evidence" *ngIf="afterLastAnswer">
          <div class="evidence-label">Live evidence from AFTER endpoint</div>
          <div class="evidence-text">{{afterLastAnswer}}</div>
        </div>
      </section>

    </div>
  </main>

  <div class="trace-modal-backdrop" *ngIf="traceModalOpen && selectedTrace" (click)="closeTrace()">
    <div class="trace-modal" (click)="$event.stopPropagation()">
      <div class="trace-head">
        <h3>Observability: decision trace</h3>
        <button class="trace-close" (click)="closeTrace()">Close</button>
      </div>

      <div class="trace-meta">
        <div><b>Endpoint:</b> {{selectedTrace.endpoint === 'before' ? 'BEFORE (unsafe path)' : 'AFTER (safe path)'}}</div>
        <div><b>Request ID:</b> {{selectedTrace.requestId || 'N/A'}}</div>
        <div><b>Retrieval backend:</b> {{selectedTrace.retrievalBackend}}</div>
        <div><b>Question:</b> {{selectedTrace.question}}</div>
      </div>

      <div class="trace-section" *ngIf="selectedTrace.timings">
        <h4>Timing breakdown (ms)</h4>
        <div class="trace-grid">
          <div>retrieval: {{selectedTrace.timings?.retrieval_ms ?? 0}}</div>
          <div>embed: {{selectedTrace.timings?.embed_ms ?? 0}}</div>
          <div>search: {{selectedTrace.timings?.search_ms ?? 0}}</div>
          <div>llm: {{selectedTrace.timings?.llm_ms ?? 0}}</div>
          <div>total: {{selectedTrace.timings?.total_ms ?? 0}}</div>
        </div>
      </div>

      <div class="trace-section">
        <h4>Citations and confidence</h4>
        <div class="trace-row" *ngFor="let c of selectedTrace.citations">
          <span>{{c.doc_id}}</span>
          <span>{{formatConfidence(c.score)}}</span>
        </div>
        <div *ngIf="!selectedTrace.citations?.length" class="trace-empty">No citations returned.</div>
      </div>

      <div class="trace-section">
        <h4>Retrieved chunk scores</h4>
        <div class="trace-row" *ngFor="let rc of selectedTrace.retrievedChunks">
          <span>{{rc.doc_id}}#{{rc.chunk_id}}</span>
          <span>{{formatConfidence(rc.score)}}</span>
        </div>
        <div *ngIf="!selectedTrace.retrievedChunks?.length" class="trace-empty">No retrieval debug rows returned.</div>
      </div>

      <div class="trace-note">
        FDE production troubleshooting tip: use the Request ID to correlate this chat decision with backend chat_request logs in Container App logs.
      </div>
    </div>
  </div>
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

.trace-link {
  margin-top: 6px;
  border: none;
  background: transparent;
  color: #2563eb;
  text-decoration: underline;
  font-size: 0.74rem;
  padding: 0;
  cursor: pointer;
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

.trace-modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(17, 24, 39, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
}

.trace-modal {
  width: min(760px, 92vw);
  max-height: 86vh;
  overflow: auto;
  background: #ffffff;
  border-radius: 10px;
  border: 1px solid #d1d5db;
  padding: 12px;
}

.trace-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.trace-head h3 {
  margin: 0;
  font-size: 0.98rem;
}

.trace-close {
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: #f9fafb;
  padding: 5px 9px;
  cursor: pointer;
}

.trace-meta {
  font-size: 0.8rem;
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 10px;
}

.trace-section {
  border-top: 1px solid #e5e7eb;
  padding-top: 8px;
  margin-top: 8px;
}

.trace-section h4 {
  margin: 0 0 6px;
  font-size: 0.84rem;
}

.trace-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 5px;
  font-size: 0.78rem;
}

.trace-row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 0.77rem;
  padding: 4px 0;
  border-bottom: 1px dashed #e5e7eb;
}

.trace-empty {
  font-size: 0.76rem;
  color: #6b7280;
}

.trace-note {
  margin-top: 10px;
  font-size: 0.76rem;
  color: #374151;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 8px;
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

  traceModalOpen = false
  selectedTrace: ObsTrace | null = null

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
      next: (res: ChatResult) => {
        const data = res.data
        this.beforeMessages = [
          ...this.beforeMessages,
          {
            role: 'assistant',
            text: data.answer,
            citations: (data.citations ?? []).map(c => ({ doc_id: c.doc_id, score: c.score })),
            trace: this.buildTrace('before', msg, res)
          }
        ]
        this.beforeLastAnswer = data.answer
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
      next: (res: ChatResult) => {
        const data = res.data
        this.afterMessages = [
          ...this.afterMessages,
          {
            role: 'assistant',
            text: data.answer,
            citations: (data.citations ?? []).map(c => ({ doc_id: c.doc_id, score: c.score })),
            trace: this.buildTrace('after', msg, res)
          }
        ]
        this.afterLastAnswer = data.answer
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

  openTrace(trace: ObsTrace): void {
    this.selectedTrace = trace
    this.traceModalOpen = true
  }

  closeTrace(): void {
    this.traceModalOpen = false
    this.selectedTrace = null
  }

  private buildTrace(endpoint: 'before' | 'after', question: string, result: ChatResult): ObsTrace {
    const data = result.data
    return {
      endpoint,
      requestId: result.requestId,
      question,
      answer: data.answer,
      retrievalBackend: data.retrieval_backend,
      timings: data.timings,
      citations: data.citations ?? [],
      retrievedChunks: data.retrieved_chunks ?? [],
    }
  }
}
