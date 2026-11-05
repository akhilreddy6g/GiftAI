import type {
  ChatRead,
  ChatTurn,
  MessageRead,
  ProductRead,
  RecommendationRead,
} from '../app/core/api/api-types';
import type { AppConfig } from '../app/core/config/app-config';

export const TEST_CONFIG: AppConfig = {
  apiUrl: 'http://api.test',
  supabaseUrl: 'https://project.supabase.test',
  supabaseAnonKey: 'anon-key',
};

export const API = TEST_CONFIG.apiUrl;

export function chat(overrides: Partial<ChatRead> = {}): ChatRead {
  return {
    id: 'chat-1',
    recipient_id: null,
    title: 'New chat',
    title_is_custom: false,
    occasion: null,
    occasion_date: null,
    budget_min_usd: null,
    budget_max_usd: null,
    created_at: '2026-11-01T10:00:00Z',
    updated_at: '2026-11-01T10:00:00Z',
    ...overrides,
  };
}

export function message(overrides: Partial<MessageRead> = {}): MessageRead {
  return {
    id: 'message-1',
    role: 'user',
    content: 'Hello',
    created_at: '2026-11-01T10:00:00Z',
    ...overrides,
  };
}

export function turn(overrides: Partial<ChatTurn> = {}): ChatTurn {
  return {
    message: message({ id: 'sent', content: 'For my sister' }),
    reply: message({ id: 'reply', role: 'assistant', content: 'What does she enjoy?' }),
    recommendations: [],
    add_all_to_cart_url: null,
    order_by: null,
    chat: chat({ updated_at: '2026-11-05T10:00:00Z' }),
    ...overrides,
  };
}

export function product(overrides: Partial<ProductRead> = {}): ProductRead {
  const asin = overrides.asin ?? 'B000COFFEE';
  return {
    asin,
    title: 'Pour-over coffee kit',
    brand: 'Brewline',
    main_category: 'Home & Kitchen',
    category_path: ['Home & Kitchen', 'Coffee'],
    image_url: `https://images.test/${asin}.jpg`,
    price_2023: '34.99',
    rating_average: 4.62,
    rating_count: 1234,
    short_description: null,
    amazon_url: `https://www.amazon.com/dp/${asin}`,
    amazon_search_url: 'https://www.amazon.com/s?k=Pour-over+coffee+kit',
    ...overrides,
  };
}

export function pick(overrides: Partial<RecommendationRead> = {}): RecommendationRead {
  const item = overrides.product ?? product();
  return {
    id: 'pick-1',
    message_id: 'reply',
    rank: 1,
    reason: 'She loves slow mornings and good coffee.',
    rules: [{ id: 'R-002', kind: 'do', rule: 'Choose something they will use often.' }],
    rating: null,
    availability: { status: 'unverified', found_votes: 0, not_found_votes: 0, your_vote: null },
    add_to_cart_url: `https://www.amazon.com/gp/aws/cart/add.html?ASIN.1=${item.asin}&Quantity.1=1`,
    product: item,
    ...overrides,
  };
}

export function errorBody(code: string, message: string) {
  return { error: { code, message, request_id: 'req-1' } };
}
