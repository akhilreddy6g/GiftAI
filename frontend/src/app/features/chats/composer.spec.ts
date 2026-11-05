import { TestBed } from '@angular/core/testing';

import { Composer } from './composer';

describe('Composer', () => {
  function setup() {
    const fixture = TestBed.createComponent(Composer);
    const sent: string[] = [];
    fixture.componentInstance.send.subscribe((text) => sent.push(text));
    fixture.detectChanges();
    const textarea: HTMLTextAreaElement = fixture.nativeElement.querySelector('textarea');
    const button: HTMLButtonElement = fixture.nativeElement.querySelector('button[type=submit]');
    const type = (value: string) => {
      textarea.value = value;
      textarea.dispatchEvent(new Event('input'));
      fixture.detectChanges();
    };
    const press = (init: KeyboardEventInit) => {
      const event = new KeyboardEvent('keydown', { key: 'Enter', cancelable: true, ...init });
      textarea.dispatchEvent(event);
      fixture.detectChanges();
      return event;
    };
    return { fixture, sent, textarea, button, type, press };
  }

  it('sends the trimmed text on Enter and clears the box', () => {
    const { sent, textarea, type, press } = setup();
    type('  A gift for Mom  ');

    const event = press({});

    expect(event.defaultPrevented).toBe(true);
    expect(sent).toEqual(['A gift for Mom']);
    expect(textarea.value).toBe('');
  });

  it('starts a new line on Shift+Enter', () => {
    const { sent, type, press } = setup();
    type('First line');

    const event = press({ shiftKey: true });

    expect(event.defaultPrevented).toBe(false);
    expect(sent).toEqual([]);
  });

  it('cannot send an empty message', () => {
    const { sent, button, type, press } = setup();
    type('   ');

    press({});

    expect(button.disabled).toBe(true);
    expect(sent).toEqual([]);
  });

  it('holds the text while busy', () => {
    const { fixture, sent, button, type, press } = setup();
    fixture.componentRef.setInput('busy', true);
    type('Hello');

    press({});

    expect(button.disabled).toBe(true);
    expect(sent).toEqual([]);
  });

  it('shows the character count near the limit', () => {
    const { fixture, type } = setup();
    expect(fixture.nativeElement.textContent).toContain('Enter to send');

    type('x'.repeat(1850));

    expect(fixture.nativeElement.textContent).toContain('1850 of 2000 characters');
  });

  it('puts text back after a failed send', () => {
    const { fixture, textarea } = setup();

    fixture.componentInstance.restore('Try again');
    fixture.detectChanges();

    expect(textarea.value).toBe('Try again');
  });
});
