import {
  ChangeDetectionStrategy,
  Component,
  type OnInit,
  inject,
  input,
  output,
  signal,
  viewChild,
} from '@angular/core';
import { Router, RouterLink, RouterLinkActive } from '@angular/router';

import { ApiClient } from '../../core/api/api-client';
import { ApiError } from '../../core/api/api-error';
import { AuthService } from '../../core/auth/auth.service';
import { ConfirmDialog } from '../../core/ui/confirm-dialog';
import { Icon } from '../../core/ui/icon';
import { formatChatDate } from '../chats/chat-dates';
import { ChatsStore } from '../chats/chats.store';
import { AccountMenu } from './account-menu';

/** The chat list with the account controls, shown as a sidebar or inside the drawer. */
@Component({
  selector: 'app-sidebar',
  imports: [RouterLink, RouterLinkActive, Icon, AccountMenu, ConfirmDialog],
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'flex h-full min-h-0 flex-col' },
  templateUrl: './sidebar.html',
})
export class Sidebar implements OnInit {
  /** True inside the mobile drawer, which adds a close button. */
  readonly inDrawer = input(false);
  readonly closeRequested = output();

  protected readonly store = inject(ChatsStore);
  private readonly auth = inject(AuthService);
  private readonly api = inject(ApiClient);
  private readonly router = inject(Router);
  private readonly deleteDialog = viewChild.required<ConfirmDialog>('deleteAccountDialog');

  protected readonly formatDate = formatChatDate;
  protected readonly deletingAccount = signal(false);
  protected readonly deleteAccountError = signal<string | null>(null);

  ngOnInit(): void {
    void this.store.ensureLoaded();
  }

  protected retry(): void {
    void this.store.ensureLoaded();
  }

  protected async signOut(): Promise<void> {
    await this.auth.signOut();
    await this.router.navigateByUrl('/sign-in');
  }

  protected askToDeleteAccount(): void {
    this.deleteAccountError.set(null);
    this.deleteDialog().open();
  }

  protected async deleteAccount(): Promise<void> {
    this.deletingAccount.set(true);
    this.deleteAccountError.set(null);
    try {
      await this.api.delete('/api/v1/me', {});
      this.deleteDialog().close();
      await this.signOut();
    } catch (error) {
      this.deleteAccountError.set(ApiError.from(error).message);
    } finally {
      this.deletingAccount.set(false);
    }
  }
}
