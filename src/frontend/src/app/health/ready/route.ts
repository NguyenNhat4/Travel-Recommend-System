import { log } from '../../../lib/logger';

const backendBaseUrl = () => (process.env.BACKEND_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');

export async function GET() {
  try {
    const upstream = await fetch(`${backendBaseUrl()}/health/ready`, { cache: 'no-store' });
    const body = await upstream.text();
    log.debug('bff.health', { probe: 'ready', status: upstream.status });

    return new Response(body, {
      status: upstream.status,
      headers: { 'content-type': upstream.headers.get('content-type') || 'application/json' },
    });
  } catch (error) {
    log.warn('bff.health', { probe: 'ready', outcome: 'backend_unreachable', error });
    return Response.json(
      { status: 'unavailable', ready: false },
      { status: 503, headers: { 'cache-control': 'no-store' } },
    );
  }
}
