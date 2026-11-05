import type { ChatRead, ChatTurn, MessageRead } from '../app/core/api/api-types';
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

export function errorBody(code: string, message: string) {
  return { error: { code, message, request_id: 'req-1' } };
}
