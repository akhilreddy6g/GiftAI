import { TestBed } from '@angular/core/testing';

import { AuthService } from '../../core/auth/auth.service';
import { FakeAuth } from '../../../testing/fake-auth';
import { AccountMenu } from './account-menu';

describe('AccountMenu', () => {
  function setup() {
    const auth = new FakeAuth();
    auth.signIn('akhil@example.com');
    TestBed.configureTestingModule({ providers: [{ provide: AuthService, useValue: auth }] });
    const fixture = TestBed.createComponent(AccountMenu);
    const events: string[] = [];
    fixture.componentInstance.signOut.subscribe(() => events.push('signOut'));
    fixture.componentInstance.deleteAccount.subscribe(() => events.push('deleteAccount'));
    fixture.detectChanges();
    const element: HTMLElement = fixture.nativeElement;
    const button = (text: string) =>
      [...element.querySelectorAll('button')].find((b) => b.textContent?.includes(text))!;
    const press = (text: string) => {
      button(text).click();
      fixture.detectChanges();
    };
    return { fixture, element, events, button, press };
  }

  it('shows the email, and opens the menu in place when pressed', () => {
    const { element, button, press } = setup();
    const trigger = button('akhil@example.com');
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
    expect(element.textContent).not.toContain('Log out');

    press('akhil@example.com');

    expect(trigger.getAttribute('aria-expanded')).toBe('true');
    expect(element.querySelector('app-theme-picker')).not.toBeNull();
    expect(element.textContent).toContain('Log out');
    expect(element.textContent).not.toContain('Delete account');
  });

  it('keeps Delete account under More', () => {
    const { events, press, button } = setup();
    press('akhil@example.com');

    press('More');
    expect(button('More').getAttribute('aria-expanded')).toBe('true');
    press('Delete account');

    expect(events).toEqual(['deleteAccount']);
  });

  it('logs out', () => {
    const { events, element, press } = setup();
    press('akhil@example.com');

    press('Log out');

    expect(events).toEqual(['signOut']);
    expect(element.textContent).not.toContain('Log out');
  });

  it('closes on Escape and returns focus to the email', () => {
    const { fixture, element, button, press } = setup();
    press('akhil@example.com');

    element.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    fixture.detectChanges();

    expect(element.textContent).not.toContain('Log out');
    expect(document.activeElement).toBe(button('akhil@example.com'));
  });

  it('closes when clicking elsewhere on the page', () => {
    const { fixture, element, press } = setup();
    press('akhil@example.com');

    document.body.click();
    fixture.detectChanges();

    expect(element.textContent).not.toContain('Log out');
  });
});
