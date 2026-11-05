import {
  ChangeDetectionStrategy,
  Component,
  type ElementRef,
  computed,
  input,
  output,
  signal,
  viewChild,
} from '@angular/core';

import { Icon } from '../../core/ui/icon';
import { MAX_MESSAGE_LENGTH } from './conversation';

/** Show the character count once a message gets this close to the limit. */
const COUNTER_THRESHOLD = MAX_MESSAGE_LENGTH - 200;

/** The message box: Enter sends, Shift+Enter starts a new line. */
@Component({
  selector: 'app-composer',
  imports: [Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <form
      class="flex items-end gap-2 rounded-2xl border border-line-strong bg-surface p-2 focus-within:outline-2 focus-within:outline-accent"
      (submit)="submit($event)"
    >
      <label [for]="inputId()" class="sr-only">{{ label() }}</label>
      <textarea
        #textarea
        [id]="inputId()"
        rows="1"
        class="max-h-48 min-h-11 flex-1 resize-none bg-transparent px-2 py-2.5 text-base text-ink [field-sizing:content] placeholder:text-ink-muted focus:outline-none"
        [placeholder]="placeholder()"
        [attr.maxlength]="maxLength"
        [attr.aria-describedby]="showCounter() ? inputId() + '-count' : inputId() + '-hint'"
        [value]="draft()"
        (input)="draft.set(textarea.value)"
        (keydown.enter)="onEnter($event)"
      ></textarea>
      <button
        type="submit"
        class="btn btn-primary size-11 shrink-0 px-0"
        [disabled]="busy() || !canSend()"
        aria-label="Send message"
      >
        <app-icon name="send" />
      </button>
    </form>
    <p class="mt-1.5 px-2 text-xs text-ink-muted">
      @if (showCounter()) {
        <span [id]="inputId() + '-count'">{{ draft().length }} of {{ maxLength }} characters</span>
      } @else {
        <span [id]="inputId() + '-hint'">Enter to send, Shift+Enter for a new line.</span>
      }
    </p>
  `,
})
export class Composer {
  readonly inputId = input('message');
  readonly label = input('Message');
  readonly placeholder = input('Write a message');
  /** While true, the text can still be edited but not sent. */
  readonly busy = input(false);

  readonly send = output<string>();

  protected readonly maxLength = MAX_MESSAGE_LENGTH;
  protected readonly draft = signal('');
  protected readonly canSend = computed(() => this.draft().trim().length > 0);
  protected readonly showCounter = computed(() => this.draft().length >= COUNTER_THRESHOLD);

  private readonly textarea = viewChild.required<ElementRef<HTMLTextAreaElement>>('textarea');

  /** Puts text back, for example after a send failed. */
  restore(text: string): void {
    this.draft.set(text);
    this.focus();
  }

  focus(): void {
    this.textarea().nativeElement.focus();
  }

  protected onEnter(event: Event): void {
    const key = event as KeyboardEvent;
    // Shift+Enter adds a line; Enter while composing (IME) confirms the composition.
    if (key.shiftKey || key.isComposing) return;
    event.preventDefault();
    this.submit();
  }

  protected submit(event?: Event): void {
    event?.preventDefault();
    const text = this.draft().trim();
    if (!text || this.busy()) return;
    this.send.emit(text);
    this.draft.set('');
  }
}
