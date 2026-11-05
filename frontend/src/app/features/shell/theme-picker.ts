import { ChangeDetectionStrategy, Component, inject } from '@angular/core';

import { type ThemePreference, ThemeService } from '../../core/theme/theme.service';
import { Icon, type IconName } from '../../core/ui/icon';

const OPTIONS: { value: ThemePreference; label: string; icon: IconName }[] = [
  { value: 'light', label: 'Light', icon: 'sun' },
  { value: 'dark', label: 'Dark', icon: 'moon' },
  { value: 'system', label: 'Device', icon: 'monitor' },
];

/** Light, dark or device theme, as a group of radio buttons. */
@Component({
  selector: 'app-theme-picker',
  imports: [Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <fieldset>
      <legend class="sr-only">Theme</legend>
      <div class="grid grid-cols-3 gap-1 rounded-lg bg-surface-muted p-1">
        @for (option of options; track option.value) {
          <label
            class="flex min-h-11 cursor-pointer items-center justify-center gap-1.5 rounded-md text-sm text-ink-muted has-checked:bg-surface has-checked:font-medium has-checked:text-ink has-checked:shadow-sm has-focus-visible:outline-2 has-focus-visible:outline-accent"
          >
            <input
              type="radio"
              name="theme"
              class="sr-only"
              [value]="option.value"
              [checked]="theme.preference() === option.value"
              (change)="theme.set(option.value)"
            />
            <app-icon [name]="option.icon" [size]="16" />
            {{ option.label }}
          </label>
        }
      </div>
    </fieldset>
  `,
})
export class ThemePicker {
  protected readonly theme = inject(ThemeService);
  protected readonly options = OPTIONS;
}
