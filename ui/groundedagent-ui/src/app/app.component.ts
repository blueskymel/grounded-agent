import { Component, OnInit } from '@angular/core'
import { CommonModule } from '@angular/common'
import { FormsModule } from '@angular/forms'
import { ApiService } from './api.service'
import { ChatResponse } from './api.types'
import { ChangeDetectorRef } from '@angular/core';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
<div class="layout">
<aside class="sidebar">
  <div class="chat">

    <div class="messages">

      <div *ngFor="let m of messages">
        <div class="user" *ngIf="m.role==='user'">
          {{m.text}}
        </div>

        <div class="assistant" *ngIf="m.role==='assistant'">
          <pre>{{m.text}}</pre>
        </div>
      </div>

    </div>

    <div class="input">
      <input [(ngModel)]="draft" placeholder="Ask something..." />
      <button (click)="send()">Send</button>
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

  </div>
</main>
</div>
  `,
  styles: [`

.chat{
flex:1;
display:flex;
flex-direction:column;
padding:20px;
}

.messages{
flex:1;
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

  draft = ''

  messages:any[] = []

  citations:any[] = []

  toolCalls:any[] = []

 constructor(private api: ApiService, private cdr: ChangeDetectorRef) {}

  ngOnInit(){}

  send() {
    const msg = this.draft.trim();
    if (!msg) return;

    this.messages = [...this.messages, { role: 'user', text: msg }];
    this.draft = '';

    this.api.chat(msg).subscribe((res: ChatResponse) => {
    this.messages = [...this.messages, { role: 'assistant', text: res.answer }];
    this.citations = res.citations ?? [];
    this.toolCalls = res.tool_calls ?? [];
    this.cdr.detectChanges();
    });

 }
}