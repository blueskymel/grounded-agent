import { Component, OnInit, ChangeDetectorRef, ElementRef, ViewChild } from '@angular/core'
import { CommonModule } from '@angular/common'
import { FormsModule } from '@angular/forms'
import { HttpErrorResponse } from '@angular/common/http'
import { ApiService, ChatResult } from './api.service'
import { ChatResponse, DecisionAudit } from './api.types'

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
  decisionReason?: string
  answer: string
  retrievalBackend: string
  timings?: ChatResponse['timings']
  citations: ChatResponse['citations']
  retrievedChunks: ChatResponse['retrieved_chunks']
  decisionAudit?: DecisionAudit
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

        <div class="messages" #beforeMessagesContainer>
          <div *ngFor="let m of beforeMessages" class="msg-row" [class.user-row]="m.role === 'user'">
            <div class="bubble" [class.user-bubble]="m.role === 'user'" [class.assistant-bubble]="m.role === 'assistant'">
              <div class="bubble-text">{{m.text}}</div>
              <button *ngIf="m.role === 'assistant' && m.trace" class="trace-link" (click)="openTrace(m.trace)">
                Decision trace
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

        <div class="messages" #afterMessagesContainer>
          <div *ngFor="let m of afterMessages" class="msg-row" [class.user-row]="m.role === 'user'">
            <div class="bubble" [class.user-bubble]="m.role === 'user'" [class.assistant-bubble]="m.role === 'assistant'">
              <div class="bubble-text">{{m.text}}</div>
              <button *ngIf="m.role === 'assistant' && m.trace" class="trace-link" (click)="openTrace(m.trace)">
                Decision trace
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

      <section class="explain-card neutral-card">
        <h3>Hallucination vs not hallucination</h3>
        <ul>
          <li><b>Hallucination:</b> the answer states facts that are not supported by retrieved runbook evidence.</li>
          <li><b>Not hallucination:</b> the answer is explicitly grounded in retrieved chunks, or the model refuses when evidence is insufficient.</li>
          <li><b>Looks correct is not enough:</b> even plausible text is unsafe if it cannot be traced to cited docs.</li>
          <li><b>In this demo:</b> BEFORE may fabricate policy details; AFTER should cite evidence or say it cannot answer.</li>
        </ul>
      </section>

      <section class="explain-card neutral-card">
        <h3>Try prompts that usually produce stronger citations</h3>
        <div class="example-list">
          <div class="example-item" *ngFor="let ex of citationExamples">
            <div class="example-label">{{ex.label}}</div>
            <div class="example-prompt">{{ex.prompt}}</div>
            <div class="example-actions">
              <button (click)="runExampleAfter(ex.prompt)" [disabled]="apiStatus === 'down' || afterSending">Run in AFTER</button>
              <button (click)="runExampleBefore(ex.prompt)" [disabled]="apiStatus === 'down' || beforeSending">Run in BEFORE</button>
            </div>
          </div>
        </div>
      </section>

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
        <h3>Decision Trace</h3>
        <button class="trace-close" (click)="closeTrace()">Close</button>
      </div>

      <div class="trace-meta">
        <div><b>Endpoint:</b> {{selectedTrace.endpoint === 'before' ? 'BEFORE (unsafe path)' : 'AFTER (safe path)'}}</div>
        <div><b>Request ID:</b> {{selectedTrace.requestId || 'N/A'}}</div>
        <div><b>Retrieval backend:</b> {{selectedTrace.retrievalBackend}}</div>
        <div><b>Question:</b> {{selectedTrace.question}}</div>
        <div>
          <b>Decision Reason:</b>
          <span [class]="decisionReasonClass(selectedTrace)">{{selectedTrace.decisionReason || 'N/A'}}</span>
        </div>
      </div>

      <div class="trace-section" *ngIf="selectedTrace.decisionAudit">
        <h4>Decision Basis</h4>
        <div class="trace-grid">
          <div>mode: {{selectedTrace.decisionAudit.mode}}</div>
          <div>refusal: {{selectedTrace.decisionAudit.refusal_triggered ? 'yes' : 'no'}}</div>
          <div>max score: {{formatConfidence(selectedTrace.decisionAudit.max_citation_score)}}</div>
          <div>safe threshold: {{formatConfidence(selectedTrace.decisionAudit.safe_min_confidence)}}</div>
          <div>display threshold: {{formatConfidence(selectedTrace.decisionAudit.min_display_score)}}</div>
          <div>safe chunks: {{selectedTrace.decisionAudit.safe_chunk_count}} / {{selectedTrace.decisionAudit.raw_chunk_count}}</div>
          <div>blocked chunks: {{selectedTrace.decisionAudit.blocked_chunk_count}}</div>
          <div>displayable citations: {{selectedTrace.decisionAudit.displayable_citation_count}}</div>
        </div>
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
        Use Request ID to correlate this trace with backend chat_request and chat_decision_audit logs in Container App logs.
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

.reason-refused {
  color: #b91c1c;
  font-weight: 700;
}

.reason-accepted {
  color: #166534;
  font-weight: 700;
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

.example-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.example-item {
  border: 1px solid #d1d5db;
  border-radius: 8px;
  background: #ffffff;
  padding: 8px;
}

.example-label {
  font-size: 0.74rem;
  font-weight: 700;
  color: #374151;
  margin-bottom: 4px;
}

.example-prompt {
  font-size: 0.8rem;
  line-height: 1.4;
  color: #111827;
  margin-bottom: 7px;
}

.example-actions {
  display: flex;
  gap: 8px;
}

.example-actions button {
  font-size: 0.75rem;
  padding: 5px 8px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: #f9fafb;
  cursor: pointer;
}

.example-actions button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
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
  @ViewChild('beforeMessagesContainer') beforeMessagesContainer?: ElementRef<HTMLDivElement>
  @ViewChild('afterMessagesContainer') afterMessagesContainer?: ElementRef<HTMLDivElement>

  apiStatus: 'checking' | 'up' | 'down' = 'checking'

  citationExamples = [
    {
      label: 'P1 process scope',
      prompt: 'Based only on the runbooks, summarize the P1 incident response steps and include concrete escalation checkpoints.'
    },
    {
      label: 'Communication cadence',
      prompt: 'What communication cadence is required for a P1 incident, and who must be updated according to the runbooks?'
    },
    {
      label: 'Rollback criteria',
      prompt: 'List the deployment rollback criteria and immediate actions from the incident runbooks.'
    },
    {
      label: 'Handoff requirements',
      prompt: 'What on-call handoff requirements are documented for critical incidents?'
    },
    {
      label: 'Retail payment degradation',
      prompt: 'According to the runbooks, what immediate actions and escalation thresholds apply when retail payment gateway latency spikes?'
    },
    {
      label: 'Retail promo mismatch',
      prompt: 'What is the diagnosis and mitigation workflow for a POS promo price mismatch incident?'
    },
    {
      label: 'Quant data gap controls',
      prompt: 'In the quant market data gap runbook, what immediate risk controls should be applied before trading resumes?'
    },
    {
      label: 'Quant reconciliation',
      prompt: 'What thresholds trigger escalation in the quant order reconciliation runbook?'
    },
    {
      label: 'Quant risk breach',
      prompt: 'What containment and exit criteria are required after a quant risk limit breach?'
    },
    {
      label: '🔓 HALLUCINATION: Data breach (not documented)',
      prompt: 'Our systems seem compromised. What is our data breach response and containment procedure?'
    },
    {
      label: '🔓 HALLUCINATION: Disaster recovery (not documented)',
      prompt: 'We need to execute our disaster recovery plan. What are the step-by-step recovery procedures?'
    },
    {
      label: '🔓 HALLUCINATION: Compliance audit (not documented)',
      prompt: 'We have an unannounced compliance audit scheduled. What is our audit response and documentation checklist?'
    }
  ]

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
    this.beforeMessages = [
      ...this.beforeMessages,
      { role: 'user', text: msg },
      { role: 'assistant', text: 'Contacting BEFORE endpoint...' }
    ]
    this.cdr.detectChanges()
    this.scrollToBottom('before')

    this.api.chatBefore(msg).subscribe({
      next: (res: ChatResult) => {
        const data = res.data
        const updated: DemoMessage = {
          role: 'assistant',
          text: data.answer,
          citations: (data.citations ?? []).map(c => ({ doc_id: c.doc_id, score: c.score })),
          trace: this.buildTrace('before', msg, res)
        }
        this.beforeMessages = this.replaceLastMessage(this.beforeMessages, updated)
        this.beforeLastAnswer = data.answer
        this.beforeSending = false
        this.cdr.detectChanges()
        this.scrollToBottom('before')
      },
      error: (err) => {
        this.beforeMessages = this.replaceLastMessage(this.beforeMessages, {
          role: 'assistant',
          text: this.formatRequestError('BEFORE', err)
        })
        this.beforeSending = false
        this.cdr.detectChanges()
        this.scrollToBottom('before')
      }
    })
  }

  sendAfter() {
    const msg = this.afterDraft.trim()
    if (!msg || this.afterSending || this.apiStatus === 'down') return

    this.afterSending = true
    this.afterDraft = ''
    this.afterMessages = [
      ...this.afterMessages,
      { role: 'user', text: msg },
      { role: 'assistant', text: 'Contacting AFTER endpoint...' }
    ]
    this.cdr.detectChanges()
    this.scrollToBottom('after')

    this.api.chatAfter(msg).subscribe({
      next: (res: ChatResult) => {
        const data = res.data
        const updated: DemoMessage = {
          role: 'assistant',
          text: data.answer,
          citations: (data.citations ?? []).map(c => ({ doc_id: c.doc_id, score: c.score })),
          trace: this.buildTrace('after', msg, res)
        }
        this.afterMessages = this.replaceLastMessage(this.afterMessages, updated)
        this.afterLastAnswer = data.answer
        this.afterSending = false
        this.cdr.detectChanges()
        this.scrollToBottom('after')
      },
      error: (err) => {
        this.afterMessages = this.replaceLastMessage(this.afterMessages, {
          role: 'assistant',
          text: this.formatRequestError('AFTER', err)
        })
        this.afterSending = false
        this.cdr.detectChanges()
        this.scrollToBottom('after')
      }
    })
  }

  runExampleBefore(prompt: string): void {
    if (this.apiStatus === 'down' || this.beforeSending) return
    this.beforeDraft = prompt
    this.sendBefore()
  }

  runExampleAfter(prompt: string): void {
    if (this.apiStatus === 'down' || this.afterSending) return
    this.afterDraft = prompt
    this.sendAfter()
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

  private replaceLastMessage(messages: DemoMessage[], replacement: DemoMessage): DemoMessage[] {
    if (!messages.length) return [replacement]
    const updated = [...messages]
    updated[updated.length - 1] = replacement
    return updated
  }

  private formatRequestError(endpoint: 'BEFORE' | 'AFTER', err: unknown): string {
    if ((err as { name?: string } | null)?.name === 'TimeoutError') {
      return `${endpoint} request timed out. API may be cold-starting; retry in a few seconds.`
    }

    const httpErr = err as HttpErrorResponse
    if (httpErr?.status === 0) {
      return `${endpoint} request could not reach the API. It may be down or waking up.`
    }

    if (httpErr?.status >= 500) {
      return `${endpoint} endpoint returned server error (${httpErr.status}). Please retry.`
    }

    return `Request failed for ${endpoint} endpoint.`
  }

  private buildTrace(endpoint: 'before' | 'after', question: string, result: ChatResult): ObsTrace {
    const data = result.data
    const reason = this.formatDecisionReason(data.decision_audit?.refusal_reason)
    return {
      endpoint,
      requestId: result.requestId || data.request_id,
      question,
      decisionReason: reason,
      answer: data.answer,
      retrievalBackend: data.retrieval_backend,
      timings: data.timings,
      citations: data.citations ?? [],
      retrievedChunks: data.retrieved_chunks ?? [],
      decisionAudit: data.decision_audit,
    }
  }

  private formatDecisionReason(reason?: string): string {
    if (!reason) return 'Answer accepted: evidence met policy threshold'

    const map: Record<string, string> = {
      safe_mode_low_citation_confidence: 'Refused: citation confidence below safe threshold',
      safe_mode_intent_evidence_mismatch: 'Refused: prompt intent not supported by retrieved evidence',
      llm_refusal: 'Refused by model guardrail response',
      prompt_injection_signals: 'Refused: direct prompt injection signal detected',
      all_retrieved_chunks_blocked_by_prompt_injection: 'Refused: retrieved chunks were blocked by prompt-injection filter',
      no_chunks_available: 'No indexed chunks available for retrieval',
      tool_path_no_retrieval: 'Tool path used; retrieval not executed',
    }

    return map[reason] ?? reason.replaceAll('_', ' ')
  }

  decisionReasonClass(trace: ObsTrace): string {
    if (trace.decisionAudit?.refusal_triggered) return 'reason-refused'
    return 'reason-accepted'
  }

  private scrollToBottom(panel: 'before' | 'after'): void {
    setTimeout(() => {
      const container = panel === 'before'
        ? this.beforeMessagesContainer?.nativeElement
        : this.afterMessagesContainer?.nativeElement

      if (!container) return
      container.scrollTop = container.scrollHeight
    }, 0)
  }
}
