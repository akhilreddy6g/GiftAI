import type { Routes } from '@angular/router';

import { requireSignedOut, requireSignIn } from './core/auth/auth.guards';

// Every page is lazy loaded, so signing in downloads only the sign-in page.
export const routes: Routes = [
  {
    path: 'sign-in',
    canActivate: [requireSignedOut],
    title: 'Sign in · GiftAI',
    loadComponent: () => import('./features/auth/sign-in.page').then((m) => m.SignInPage),
  },
  {
    path: 'auth/callback',
    title: 'Signing in · GiftAI',
    loadComponent: () =>
      import('./features/auth/auth-callback.page').then((m) => m.AuthCallbackPage),
  },
  {
    path: 'reset-password',
    canActivate: [requireSignIn],
    title: 'Choose a new password · GiftAI',
    loadComponent: () =>
      import('./features/auth/reset-password.page').then((m) => m.ResetPasswordPage),
  },
  {
    path: '',
    canActivate: [requireSignIn],
    loadComponent: () => import('./features/shell/shell').then((m) => m.Shell),
    children: [
      {
        path: '',
        pathMatch: 'full',
        title: 'GiftAI',
        loadComponent: () => import('./features/chats/home.page').then((m) => m.HomePage),
      },
      {
        path: 'chats/:chatId',
        title: 'Chat · GiftAI',
        loadComponent: () => import('./features/chats/chat.page').then((m) => m.ChatPage),
      },
    ],
  },
  {
    path: '**',
    title: 'Page not found · GiftAI',
    loadComponent: () => import('./features/not-found.page').then((m) => m.NotFoundPage),
  },
];
