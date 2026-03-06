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

    <div class="input">
        <input
        [(ngModel)]="draft"
        placeholder="Ask something..."
        (keydown.enter)="onEnter($event)"
        />
        <button (click)="send()" [disabled]="isSending">Send</button>
    </div>

  </div>
</aside>
 <main class="main">
  <div class="side">

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

    <div *ngIf="retrievedChunks?.length">
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

  constructor(private api: ApiService, private cdr: ChangeDetectorRef) {}

  ngOnInit(){}

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
        text: 'Error: request failed.'
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
}