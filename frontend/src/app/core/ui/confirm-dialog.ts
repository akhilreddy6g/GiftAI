import {
  ChangeDetectionStrategy,
  Component,
  type ElementRef,
  input,
  output,
  viewChild,
} from '@angular/core';

/**
 * A modal question with a confirm and a cancel button, built on the native <dialog>, which
 * traps focus, closes on Escape and returns focus to the button that opened it.
 */
@Component({
  selector: 'app-confirm-dialog',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <dialog
      #dialog
      class="m-auto w-[min(28rem,calc(100vw-2rem))] rounded-2xl border border-line bg-surface p-0 text-ink shadow-xl backdrop:bg-black/50"
      [attr.aria-labelledby]="id() + '-title'"
      [attr.aria-describedby]="id() + '-message'"
      (cancel)="onCancel($event)"
    >
      <div class="p-6">
        <h2 [id]="id() + '-title'" class="text-lg font-semibold">{{ heading() }}</h2>
        <p [id]="id() + '-message'" class="mt-2 text-ink-muted">{{ message() }}</p>
        @if (error(); as text) {
          <p class="alert-error mt-4" role="alert">{{ text }}</p>
        }
        <div class="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <button type="button" class="btn btn-secondary" [disabled]="busy()" (click)="close()">
            Cancel
          </button>
          <button
            type="button"
            class="btn"
            [class.btn-danger]="danger()"
            [class.btn-primary]="!danger()"
            [disabled]="busy()"
            (click)="confirmed.emit()"
          >
            {{ busy() ? busyLabel() : confirmLabel() }}
          </button>
        </div>
      </div>
    </dialog>
  `,
})
export class ConfirmDialog {
  /** Prefix for element ids, unique on the page. */
  readonly id = input.required<string>();
  readonly heading = input.required<string>();
  readonly message = input.required<string>();
  readonly confirmLabel = input('Confirm');
  readonly busyLabel = input('Working…');
  readonly danger = input(false);
  readonly busy = input(false);
  readonly error = input<string | null>(null);

  readonly confirmed = output();

  private readonly dialog = viewChild.required<ElementRef<HTMLDialogElement>>('dialog');

  open(): void {
    const dialog = this.dialog().nativeElement;
    if (!dialog.open) dialog.showModal();
  }

  close(): void {
    this.dialog().nativeElement.close();
  }

  protected onCancel(event: Event): void {
    // Escape does nothing while the action runs, so its result is never missed.
    if (this.busy()) event.preventDefault();
  }
}
