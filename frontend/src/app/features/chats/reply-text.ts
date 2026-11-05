const NUMBERED_LINE = /^\s*\d+\.\s/;

/**
 * The reply as shown above its gift cards. The saved reply lists the picks as numbered
 * lines (the assistant reads them back next turn); the cards show them better, so those
 * paragraphs are left out when the cards are there.
 */
export function replyTextAboveCards(content: string): string {
  return content
    .split(/\n{2,}/)
    .filter((paragraph) => !paragraph.split('\n').every((line) => NUMBERED_LINE.test(line)))
    .join('\n\n')
    .trim();
}
