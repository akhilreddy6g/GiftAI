import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink } from '@angular/router';

import { AuthLayout } from './auth/auth-layout';

@Component({
  selector: 'app-not-found-page',
  imports: [AuthLayout, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <app-auth-layout
      heading="We couldn't find that page"
      intro="The link may be old, or the page may have moved."
    >
      <a routerLink="/" class="btn btn-primary w-full">Go to your chats</a>
    </app-auth-layout>
  `,
})
export class NotFoundPage {}
