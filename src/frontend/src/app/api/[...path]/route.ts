import { NextResponse } from 'next/server';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

type RouteContext = {
  params: Promise<{ path: string[] }>;
};

function backendUrl(path: string[], search: string) {
  const baseUrl = process.env.BACKEND_BASE_URL;
  if (!baseUrl) return null;

  const base = baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`;
  const target = new URL(`api/${path.join('/')}`, base);
  target.search = search;
  return target;
}

async function proxy(request: Request, context: RouteContext) {
  const { path } = await context.params;
  const target = backendUrl(path, new URL(request.url).search);

  if (!target) {
    return NextResponse.json(
      { error: 'Backend service is not configured' },
      { status: 503 },
    );
  }

  const headers = new Headers(request.headers);
  headers.delete('host');
  headers.delete('content-length');

  const body = ['GET', 'HEAD'].includes(request.method)
    ? undefined
    : await request.arrayBuffer();

  try {
    const response = await fetch(target, {
      method: request.method,
      headers,
      body,
      cache: 'no-store',
      signal: request.signal,
    });

    const responseHeaders = new Headers();
    for (const header of ['content-type', 'cache-control', 'location']) {
      const value = response.headers.get(header);
      if (value) responseHeaders.set(header, value);
    }

    return new NextResponse(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: responseHeaders,
    });
  } catch (error) {
    console.error('Backend proxy error', error);
    return NextResponse.json(
      { error: 'Backend service unavailable' },
      { status: 502 },
    );
  }
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const HEAD = proxy;
