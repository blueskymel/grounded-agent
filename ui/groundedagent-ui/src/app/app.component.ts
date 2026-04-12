import { Component, OnInit, ElementRef, ViewChild, ChangeDetectorRef } from '@angular/core'
import { CommonModule } from '@angular/common'
import { FormsModule } from '@angular/forms'
import { ApiService } from './api.service'
import { ChatResponse } from './api.types'

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
<div class="layout">
<aside class="sidebar">
  <div class="chat">

    <div class="messages" #messagesEl>

      <div *ngFor="let m of messages">
        <div class="user" *ngIf="m.role==='user'">
          {{m.text}}
        </div>

        <div class="assistant" *ngIf="m.role==='assistant'">
          <pre>{{m.text}}</pre>

          <div *ngIf="m.citations?.length">
            <small>Citations:</small>
            <div *ngFor="let c of m.citations">
              {{c.doc_id}}#{{c.chunk_id}}
            </div>
          </div>

        </div>
      </div>

    </div>

    <div *ngIf="apiStatus === 'down'" class="api-banner">
      ⚠️ <strong>API not reachable.</strong> The backend is not running. To use the chat, start the local API — see the demo guide on the right.
    </div>

    <div class="input">
        <input
        [(ngModel)]="draft"
        placeholder="Ask something..."
        (keydown.enter)="onEnter($event)"
        [disabled]="apiStatus === 'down'"
        />
        <button (click)="send()" [disabled]="isSending || apiStatus === 'down'">Send</button>
    </div>

  </div>
</aside>
 <main class="main">
  <div class="side">

    <!-- FDE Demo Instructions -->
    <div class="demo-guide">
      <div class="demo-header" (click)="guideOpen = !guideOpen">
        <span class="demo-title">The Hallucination Problem &amp; How We Fixed It</span>
        <span class="demo-toggle">{{ guideOpen ? '▲ collapse' : '▼ expand' }}</span>
      </div>

      <div *ngIf="guideOpen" class="demo-body">

        <p class="demo-intro">
          <strong>GroundedAgent</strong> is an AI copilot that answers IT questions using company runbooks.
          The problem: the AI was <em>making up answers</em> instead of admitting when information was missing.
          Here's the issue and the fix, side-by-side.
        </p>

        <!-- Before / After side-by-side -->
        <div class="ba-grid">

          <!-- BEFORE -->
          <div class="ba-col">
            <div class="ba-label bad">❌ Before — AI fabricates an answer</div>
            <div class="fake-thread">
              <div class="fake-user">What is the SLA for this service?</div>
              <div class="fake-bot bad-bot">
                <div class="bot-text">
                  The platform provides a <strong>99.99% uptime SLA</strong> with cross-region
                  failover in under 5 minutes. Incidents exceeding this threshold qualify for
                  service credits per the enterprise agreement.
                </div>
                <div class="hallucination-tag">⚠️ Fabricated — no SLA exists in any runbook</div>
              </div>
            </div>
          </div>

          <!-- AFTER -->
          <div class="ba-col">
            <div class="ba-label good">✅ After — AI refuses to guess</div>
            <div class="fake-thread">
              <div class="fake-user">What is the SLA for this service?</div>
              <div class="fake-bot good-bot">
                <div class="bot-text">
                  I don't have enough information in the provided runbooks to answer that.
                </div>
                <div class="grounded-tag">✅ Grounded — only answers what's in the docs</div>
              </div>
            </div>
          </div>

        </div><!-- /ba-grid -->

        <!-- The fix -->
        <div class="fix-row">
          <span class="fix-label">The fix</span>
          <span class="fix-desc">One environment variable switches the guardrail on or off:</span>
          <div class="diff-block">
            <div class="diff-remove">HALLUCINATION_DEMO_MODE=<strong>unsafe</strong> &nbsp;← fabricates answers</div>
            <div class="diff-add">HALLUCINATION_DEMO_MODE=<strong>safe</strong> &nbsp;&nbsp;&nbsp;← refuses to guess ✓</div>
          </div>
        </div>

        <!-- Automated proof -->
        <div class="proof-row">
          <div class="proof-label">🧪 Locked in by automated tests</div>
          <div class="proof-tests">
            <div class="test-pass">✓ &nbsp;test_unsafe_mode_can_hallucinate</div>
            <div class="test-pass">✓ &nbsp;test_safe_mode_refuses_missing_sla</div>
          </div>
        </div>

        <!-- Client rollout -->
        <div class="rollout-row">
          <div class="rollout-label">🌐 Works for any client</div>
          <div class="rollout-items">
            <div class="rollout-item">One codebase — the same fix ships to every client unchanged</div>
            <div class="rollout-item"><code>safe</code> is the default in all environments</div>
            <div class="rollout-item"><code>unsafe</code> is only allowed in isolated demo sandboxes</div>
          </div>
        </div>

        <!-- CTA -->
        <div class="cta-row">
          👆 Try it live — type <em>"What is the SLA for this service?"</em> in the chat
        </div>

      </div>
    </div>
    <h3>Tool Activity</h3>

    <div *ngFor="let t of toolCalls">
      <b>{{t.name}}</b>
      <pre>{{t.input | json}}</pre>
      <pre *ngIf="t.output">{{t.output | json}}</pre>
    </div>

    <h3>Citations</h3>

    <div *ngFor="let c of citations">
      <b>{{c.doc_id}}#{{c.chunk_id}}</b>
      <div>{{c.title}}</div>
      <div>{{c.snippet}}</div>
    </div>

    <h3>Retrieval Debug</h3>

    <div *ngIf="timings">
      <div><b>retrieval_ms:</b> {{timings.retrieval_ms}}</div>
      <div><b>embed_ms:</b> {{timings.embed_ms}}</div>
      <div><b>search_ms:</b> {{timings.search_ms}}</div>
      <div><b>llm_ms:</b> {{timings.llm_ms}}</div>
      <div><b>total_ms:</b> {{timings.total_ms}}</div>
    </div>

    <div *ngIf="retrievedChunks.length">
      <h4>Top Chunks</h4>
      <div *ngFor="let rc of retrievedChunks" style="margin-bottom:10px;">
        <div><b>{{rc.doc_id}}#{{rc.chunk_id}}</b></div>
        <div *ngIf="rc.score !== undefined">score: {{rc.score | number:'1.2-3'}}</div>
      </div>
    </div>    
  </div>
</main>
</div>
  `,
  styles: [`
button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.chat{
flex:1;
display:flex;
flex-direction:column;
padding:20px;
}

.messages{
flex:1;
min-height:0;
overflow:auto;
}

.user{
text-align:right;
margin:10px;
}

.assistant{
margin:10px;
background:#f3f3f3;
padding:10px;
border-radius:6px;
}

.input{
display:flex;
gap:10px;
}

input{
flex:1;
padding:10px;
}

.side{
width:100%;
border-left:1px solid #ddd;
padding:20px;
overflow:auto;
}

.layout {
  display: flex;
  height: 100vh;          /* or 100dvh */
  overflow: hidden;       /* prevents page-level horizontal scroll */
}

/* Sidebar: fixed width, never shrink */
.sidebar {
  width: 50%;           /* pick what you want */
  flex: 0 0 50%;        /* do not grow, do not shrink */
  overflow: auto;         /* sidebar scrolls if it overflows */
  border-right: 1px solid #e5e7eb;
}

/* Main: take remaining space, and IMPORTANT: min-width: 0 */
.main {
  width:50%;
  flex: 1 1 auto;
  min-width: 0;           /* this is the key to prevent squeezing/overflow bugs */
  overflow: hidden;       /* contain inner scrolling */
  display: flex;
  flex-direction: column;
}

/* If your chat area is a scroll region inside main */
.main .chat-scroll {
  width:50%;
  flex: 1 1 auto;
  min-height: 0;          /* also important for nested flex scroll */
  overflow: auto;
}

/* FDE Demo Guide */
.demo-guide {
  border: 1px solid #c7d2fe;
  border-radius: 8px;
  margin-bottom: 16px;
  background: #fafafa;
  overflow: hidden;
}
.demo-header {
  padding: 10px 14px;
  background: #ede9fe;
  border-bottom: 1px solid #c7d2fe;
  user-select: none;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.demo-title { font-weight: 700; font-size: 0.9rem; color: #4f46e5; }
.demo-toggle { font-size: 0.75rem; color: #6b7280; }
.demo-body { padding: 12px 14px; font-size: 0.8rem; }
.demo-intro { margin: 0 0 12px; color: #374151; line-height: 1.5; }

/* Before / After grid */
.ba-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 12px; }
.ba-col { display: flex; flex-direction: column; gap: 6px; }
.ba-label { font-weight: 700; font-size: 0.75rem; padding: 3px 6px; border-radius: 4px; }
.ba-label.bad  { background: #fee2e2; color: #b91c1c; }
.ba-label.good { background: #dcfce7; color: #15803d; }
.fake-thread { display: flex; flex-direction: column; gap: 4px; }
.fake-user {
  align-self: flex-end;
  background: #dbeafe;
  color: #1e40af;
  padding: 5px 8px;
  border-radius: 10px 10px 2px 10px;
  font-size: 0.75rem;
  max-width: 90%;
}
.fake-bot {
  border-radius: 2px 10px 10px 10px;
  padding: 6px 8px;
  font-size: 0.75rem;
  max-width: 95%;
}
.fake-bot.bad-bot  { background: #fef3c7; border: 1px solid #f59e0b; }
.fake-bot.good-bot { background: #f0fdf4; border: 1px solid #86efac; }
.bot-text { margin-bottom: 4px; line-height: 1.4; }
.hallucination-tag {
  font-size: 0.7rem; color: #b45309; font-style: italic;
  border-top: 1px dashed #f59e0b; padding-top: 3px; margin-top: 2px;
}
.grounded-tag {
  font-size: 0.7rem; color: #15803d; font-style: italic;
  border-top: 1px dashed #86efac; padding-top: 3px; margin-top: 2px;
}

/* The fix */
.fix-row {
  background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px;
  padding: 8px 10px; margin-bottom: 10px; display: flex; flex-direction: column; gap: 4px;
}
.fix-label { font-weight: 700; font-size: 0.78rem; color: #374151; }
.fix-desc  { font-size: 0.75rem; color: #6b7280; }
.diff-block { font-family: monospace; font-size: 0.72rem; margin-top: 2px; }
.diff-remove { background: #fee2e2; color: #b91c1c; padding: 2px 6px; border-radius: 3px; margin-bottom: 2px; }
.diff-add    { background: #dcfce7; color: #15803d; padding: 2px 6px; border-radius: 3px; }

/* Tests */
.proof-row {
  background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 6px;
  padding: 8px 10px; margin-bottom: 10px;
}
.proof-label { font-weight: 700; font-size: 0.78rem; color: #1d4ed8; margin-bottom: 4px; }
.test-pass { font-family: monospace; font-size: 0.73rem; color: #15803d; }

/* Rollout */
.rollout-row {
  background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 6px;
  padding: 8px 10px; margin-bottom: 10px;
}
.rollout-label { font-weight: 700; font-size: 0.78rem; color: #374151; margin-bottom: 4px; }
.rollout-item { font-size: 0.75rem; color: #4b5563; margin-bottom: 2px; }
.rollout-item::before { content: "→ "; color: #9ca3af; }
.rollout-item code { background: #e5e7eb; padding: 1px 4px; border-radius: 3px; }

/* CTA */
.cta-row {
  background: #fdf4ff; border: 1px solid #e9d5ff; border-radius: 6px;
  padding: 8px 10px; font-size: 0.78rem; color: #7e22ce; font-style: italic;
}
.api-banner {
  background: #fff3cd;
  border: 1px solid #ffc107;
  border-radius: 6px;
  padding: 8px 12px;
  font-size: 0.82rem;
  color: #856404;
  margin-bottom: 8px;
}
`]
})
export class AppComponent implements OnInit {

  @ViewChild('messagesEl', { static: false })
  messagesEl!: ElementRef<HTMLDivElement>

  private scrollToBottom() {

    requestAnimationFrame(() => {
      const el = this.messagesEl?.nativeElement
      if (!el) return

      el.scrollTop = el.scrollHeight
    })

  }

  draft = ''

  messages:any[] = []

  citations:any[] = []

  toolCalls:any[] = []

  retrievedChunks: any[] = []

  timings: any = null

  isSending = false

  guideOpen = true

  apiStatus: 'checking' | 'up' | 'down' = 'checking'

  constructor(private api: ApiService, private cdr: ChangeDetectorRef) {}

  ngOnInit() {
    this.api.health().subscribe({
      next: () => { this.apiStatus = 'up'; this.cdr.detectChanges() },
      error: () => { this.apiStatus = 'down'; this.cdr.detectChanges() }
    })
  }

onEnter(event: Event) {
  event.preventDefault()
  if (!this.isSending) {
    this.send()
  }
}

send() {
  const msg = this.draft.trim()
  if (!msg || this.isSending) return

  this.isSending = true

  // add user message
  this.messages = [...this.messages, { role: 'user', text: msg }]
  this.scrollToBottom()

  this.draft = ''

  // add temporary assistant message
  const thinkingMsg = {
    role: 'assistant',
    text: 'Thinking…',
    pending: true
  }

  this.messages = [...this.messages, thinkingMsg]
  this.scrollToBottom()

  this.api.chat(msg).subscribe({
    next: (res: ChatResponse) => {
      const idx = this.messages.indexOf(thinkingMsg)

      const assistantMsg = {
        role: 'assistant',
        text: res.answer,
        citations: res.citations ?? [],
        toolCalls: res.tool_calls ?? []
      }

      if (idx >= 0) {
        this.messages[idx] = assistantMsg
        this.messages = [...this.messages]
      } else {
        this.messages = [...this.messages, assistantMsg]
      }

      // keep right-hand panel working
      this.citations = res.citations ?? []
      this.toolCalls = res.tool_calls ?? []

      this.retrievedChunks = res.retrieved_chunks ?? []
      this.timings = res.timings ?? null      

      this.isSending = false
      this.scrollToBottom()
      this.cdr.detectChanges()
    },

    error: () => {
      const idx = this.messages.indexOf(thinkingMsg)

      const errorMsg = {
        role: 'assistant',
        text: 'Error: could not reach the API. Make sure the backend is running locally (see the demo guide →)'
      }

      if (idx >= 0) {
        this.messages[idx] = errorMsg
        this.messages = [...this.messages]
      } else {
        this.messages = [...this.messages, errorMsg]
      }

      this.isSending = false
      this.scrollToBottom()
      this.cdr.detectChanges()
    }
  })
}

sendStream() {

  const msg = this.draft.trim()
  if (!msg || this.isSending) return

  this.isSending = true

  this.messages = [...this.messages,{role:'user',text:msg}]
  this.draft = ''

  const assistantMsg = {
    role:'assistant',
    text:''
  }

  this.messages = [...this.messages, assistantMsg]

  this.api.streamChat(msg,

    (token:string)=>{
      assistantMsg.text += token + " "
      this.messages = [...this.messages]
      this.scrollToBottom()
    },

    ()=>{
      this.isSending = false
    }

  )

}
}