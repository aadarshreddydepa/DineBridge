import type { Config, Menu, Order } from './types'

const base = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(public code: string, message: string, public status: number) { super(message) }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${base}${path}`, { credentials: 'include', ...init })
  } catch {
    throw new ApiError('NETWORK_ERROR', 'Could not reach the restaurant. Check your connection and try again.', 0)
  }
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new ApiError(data.code || 'REQUEST_FAILED', data.message || 'Something went wrong. Please try again.', response.status)
  return data as T
}

export const api = {
  config: (outlet: string) => request<Config>(`/api/v1/outlets/${outlet}/config`),
  menu: (outlet: string) => request<Menu>(`/api/v1/outlets/${outlet}/menu`),
  access: () => request<{ outlet_id: string; table_label: string }>(`/api/v1/access`),
  orders: () => request<{ orders: Order[] }>(`/api/v1/orders`),
  order: (id: string) => request<Order>(`/api/v1/orders/${id}`),
  async post<T>(path: string, body: unknown, idempotencyKey?: string): Promise<T> {
    const { csrf_token } = await request<{ csrf_token: string }>('/api/v1/csrf')
    return request<T>(path, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrf_token,
        ...(idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {}),
      },
      body: JSON.stringify(body),
    })
  },
}
