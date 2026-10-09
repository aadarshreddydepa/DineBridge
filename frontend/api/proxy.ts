// Keeps QR and API cookies on the Vercel site origin while forwarding to Render.
export default {
  async fetch(request: Request): Promise<Response> {
    const apiOrigin = process.env.API_ORIGIN
    if (!apiOrigin) return Response.json({ code: 'GATEWAY_NOT_CONFIGURED', message: 'API_ORIGIN is missing.' }, { status: 503 })
    const incoming = new URL(request.url)
    const upstreamPath = incoming.searchParams.get('upstream') || ''
    if (!/^\/(api\/v1\/|q\/)[a-zA-Z0-9_\-/]*$/.test(upstreamPath)) {
      return Response.json({ code: 'INVALID_PATH', message: 'Invalid gateway path.' }, { status: 400 })
    }
    const target = new URL(upstreamPath, apiOrigin)
    for (const [key, value] of incoming.searchParams) if (key !== 'upstream') target.searchParams.append(key, value)
    const headers = new Headers()
    for (const name of ['accept', 'content-type', 'cookie', 'x-csrftoken', 'idempotency-key', 'origin']) {
      const value = request.headers.get(name)
      if (value) headers.set(name, value)
    }
    try {
      const upstream = await fetch(target, { method: request.method, headers, body: ['GET', 'HEAD'].includes(request.method) ? undefined : request.body, redirect: 'manual', duplex: 'half' } as RequestInit)
      const responseHeaders = new Headers()
      for (const name of ['content-type', 'set-cookie', 'location', 'cache-control', 'referrer-policy']) {
        const value = upstream.headers.get(name)
        if (value) responseHeaders.set(name, value)
      }
      responseHeaders.set('Cache-Control', 'no-store')
      return new Response(upstream.body, { status: upstream.status, headers: responseHeaders })
    } catch {
      return Response.json({ code: 'API_UNAVAILABLE', message: 'The restaurant service is temporarily unavailable.' }, { status: 502 })
    }
  },
}
