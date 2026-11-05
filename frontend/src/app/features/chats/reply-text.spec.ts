import { replyTextAboveCards } from './reply-text';

describe('replyTextAboveCards', () => {
  it('leaves out the numbered list the cards replace', () => {
    const reply = [
      'Here are some ideas for Priya.',
      '1. Coffee kit (about $35): she loves coffee.\n2. Mug (about $20): for her desk.',
      'Order by Friday, December 5 so it arrives in time for December 12.',
    ].join('\n\n');

    expect(replyTextAboveCards(reply)).toBe(
      'Here are some ideas for Priya.\n\n' +
        'Order by Friday, December 5 so it arrives in time for December 12.',
    );
  });

  it('keeps paragraphs that only start with a number', () => {
    expect(replyTextAboveCards('3 ideas below.\n\n1. A\nnot a list line')).toBe(
      '3 ideas below.\n\n1. A\nnot a list line',
    );
  });
});
