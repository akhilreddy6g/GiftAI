import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

// Outline icons on a 24px grid, drawn with the current text color. Decorative only:
// the button or link around an icon always carries the accessible name.
const PATHS = {
  menu: 'M4 6h16M4 12h16M4 18h16',
  close: 'M6 6l12 12M18 6L6 18',
  plus: 'M12 5v14M5 12h14',
  send: 'M5 12h13M13 6l6 6-6 6',
  pencil: 'M4 20h4L19 9l-4-4L4 16v4zM14 6l4 4',
  trash: 'M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3',
  chat: 'M4 5h16v11H9l-5 4V5z',
  sun: 'M12 4V2M12 22v-2M4 12H2M22 12h-2M5.6 5.6 4.2 4.2M19.8 19.8l-1.4-1.4M5.6 18.4l-1.4 1.4M19.8 4.2l-1.4 1.4M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z',
  moon: 'M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z',
  monitor: 'M3 4h18v12H3zM8 20h8M12 16v4',
  logout: 'M15 4h4v16h-4M10 8l-4 4 4 4M6 12h11',
  gift: 'M4 11h16v9H4zM3 7h18v4H3zM12 7v13M12 7C10.5 3.5 7 3.5 7 5.5S10 7 12 7zm0 0c1.5-3.5 5-3.5 5-1.5S14 7 12 7z',
  more: 'M5 12h.01M12 12h.01M19 12h.01',
  alert:
    'M12 8v5M12 16h.01M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z',
  cart: 'M3 4h2l2.4 11h10.2L20 7H6.2M9 20h.01M17 20h.01',
  external: 'M14 4h6v6M20 4l-9 9M18 14v6H4V6h6',
  search: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM20 20l-4-4',
  star: 'M12 3l2.8 5.7 6.2.9-4.5 4.4 1 6.2L12 17.3l-5.5 2.9 1-6.2L3 9.6l6.2-.9L12 3z',
  check: 'M5 12l5 5 9-10',
  'chevron-right': 'M9 6l6 6-6 6',
  'chevron-up-down': 'M8 9l4-4 4 4M8 15l4 4 4-4',
  'thumbs-up':
    'M7 10v10H4V10h3zm0 0 4-7a2 2 0 0 1 3 2l-1 4h6a2 2 0 0 1 2 2.3l-1.2 7a2 2 0 0 1-2 1.7H7',
  'thumbs-down':
    'M7 14V4H4v10h3zm0 0 4 7a2 2 0 0 0 3-2l-1-4h6a2 2 0 0 0 2-2.3l-1.2-7a2 2 0 0 0-2-1.7H7',
} as const;

export type IconName = keyof typeof PATHS;

@Component({
  selector: 'app-icon',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'inline-flex shrink-0', 'aria-hidden': 'true' },
  template: `
    <svg
      [attr.width]="size()"
      [attr.height]="size()"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="1.8"
      stroke-linecap="round"
      stroke-linejoin="round"
      focusable="false"
    >
      <path [attr.d]="path()" />
    </svg>
  `,
})
export class Icon {
  readonly name = input.required<IconName>();
  readonly size = input(20);

  protected readonly path = computed(() => PATHS[this.name()]);
}
