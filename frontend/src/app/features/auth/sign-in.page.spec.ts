import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';

import { FakeAuth } from '../../../testing/fake-auth';
import { provideTestApp } from '../../../testing/providers';
import { SignInPage } from './sign-in.page';

describe('SignInPage', () => {
  let auth: FakeAuth;

  function setup(next?: string) {
    auth = new FakeAuth();
    TestBed.configureTestingModule({ providers: provideTestApp(auth) });
    const fixture = TestBed.createComponent(SignInPage);
    if (next) fixture.componentRef.setInput('next', next);
    fixture.detectChanges();
    const element: HTMLElement = fixture.nativeElement;
    const fill = (selector: string, value: string) => {
      const input = element.querySelector<HTMLInputElement>(selector)!;
      input.value = value;
      input.dispatchEvent(new Event('input'));
    };
    const submit = async () => {
      element.querySelector('form')!.dispatchEvent(new Event('submit'));
      await fixture.whenStable();
      fixture.detectChanges();
    };
    const clickButton = (text: string) => {
      const button = [...element.querySelectorAll('button')].find((b) =>
        b.textContent?.includes(text),
      );
      button!.click();
      fixture.detectChanges();
    };
    return { fixture, element, fill, submit, clickButton };
  }

  it('signs in with a password and returns to the requested page', async () => {
    const { fill, submit } = setup('/chats/abc');
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigateByUrl').mockResolvedValue(true);

    fill('#email', ' giver@example.com ');
    fill('#password', 'secret-password');
    await submit();

    expect(auth.calls).toEqual([
      { method: 'signInWithPassword', args: ['giver@example.com', 'secret-password'] },
    ]);
    expect(navigate).toHaveBeenCalledWith('/chats/abc');
  });

  it('never redirects to another site after sign-in', async () => {
    const { fill, submit } = setup('https://evil.example');
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigateByUrl').mockResolvedValue(true);

    fill('#email', 'giver@example.com');
    fill('#password', 'secret-password');
    await submit();

    expect(navigate).toHaveBeenCalledWith('/');
  });

  it('flags an invalid email and does not call sign-in', async () => {
    const { element, fill, submit } = setup();

    fill('#email', 'not-an-email');
    await submit();

    expect(auth.calls).toEqual([]);
    expect(element.querySelector('#email')!.getAttribute('aria-invalid')).toBe('true');
    expect(element.textContent).toContain('Enter an email address');
  });

  it('shows the sign-in error to the user', async () => {
    const { element, fill, submit } = setup();
    auth.result = { ok: false, message: "That email and password don't match." };

    fill('#email', 'giver@example.com');
    fill('#password', 'wrong');
    await submit();

    expect(element.querySelector('[role=alert]')!.textContent).toContain("don't match");
  });

  it('requires a longer password when creating an account', async () => {
    const { element, fill, submit, clickButton } = setup();
    clickButton('Create an account');

    fill('#email', 'giver@example.com');
    fill('#password', 'short');
    await submit();

    expect(auth.calls).toEqual([]);
    expect(element.textContent).toContain('Use at least 8 characters.');
  });

  it('asks new users to confirm their email when Supabase requires it', async () => {
    const { element, fill, submit, clickButton } = setup();
    auth.signUpResult = { ok: true, needsEmailConfirmation: true };
    clickButton('Create an account');

    fill('#email', 'giver@example.com');
    fill('#password', 'long-enough-password');
    await submit();

    expect(element.textContent).toContain('We sent a confirmation link to giver@example.com');
  });

  it('sends a magic link without asking for a password', async () => {
    const { element, fill, submit, clickButton } = setup('/chats/abc');
    clickButton('Email me a sign-in link instead');

    expect(element.querySelector('#password')).toBeNull();
    fill('#email', 'giver@example.com');
    await submit();

    expect(auth.calls).toEqual([
      { method: 'sendMagicLink', args: ['giver@example.com', '/chats/abc'] },
    ]);
    expect(element.textContent).toContain('Check your inbox');
  });
});
