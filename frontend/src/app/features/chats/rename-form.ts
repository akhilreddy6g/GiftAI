import {
  ChangeDetectionStrategy,
  Component,
  type ElementRef,
  afterNextRender,
  input,
  output,
  signal,
  viewChild,
} from '@angular/core';

import { ApiError } from '../../core/api/api-error';

const MAX_TITLE_LENGTH = 120;

/** Edits a chat's title in place; an empty title goes back to the automatic one. */
@Component({
  selector: 'app-rename-form',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <form class="flex flex-wrap items-center gap-2" (submit)="submit($event)">
      <label for="chat-title" class="sr-only">Chat name</label>
      <input
        #field
        id="chat-title"
        class="field-input min-w-0 flex-1 basis-56"
        [value]="title()"
        [attr.maxlength]="maxLength"
        autocomplete="off"
        aria-describedby="chat-title-hint"
        (keydown.escape)="cancel()"
      />
      <div class="flex gap-2">
        <button type="submit" class="btn btn-primary" [disabled]="saving()">
          {{ saving() ? 'Saving…' : 'Save' }}
        </button>
        <button type="button" class="btn btn-secondary" [disabled]="saving()" (click)="cancel()">
          Cancel
        </button>
      </div>
      <p id="chat-title-hint" class="w-full text-xs text-ink-muted">
        Leave it empty to let GiftAI name the chat.
      </p>
      @if (error(); as message) {
        <p class="alert-error w-full" role="alert">{{ message }}</p>
      }
    </form>
  `,
})
export class RenameForm {
  readonly title = input.required<string>();
  /** Saves the new title (null for automatic); a rejection's message is shown. */
  readonly save = input.required<(title: string | null) => Promise<unknown>>();
  /** Emitted once the title is saved or editing is cancelled. */
  readonly closed = output();

  protected readonly maxLength = MAX_TITLE_LENGTH;
  protected readonly saving = signal(false);
  protected readonly error = signal<string | null>(null);
  private readonly field = viewChild.required<ElementRef<HTMLInputElement>>('field');

  constructor() {
    afterNextRender(() => this.field().nativeElement.select());
  }

  protected async submit(event: Event): Promise<void> {
    event.preventDefault();
    if (this.saving()) return;
    const value = this.field().nativeElement.value.trim();
    this.saving.set(true);
    this.error.set(null);
    try {
      await this.save()(value || null);
      this.closed.emit();
    } catch (error) {
      this.error.set(ApiError.from(error).message);
      this.field().nativeElement.focus();
    } finally {
      this.saving.set(false);
    }
  }

  protected cancel(): void {
    if (!this.saving()) this.closed.emit();
  }
}
