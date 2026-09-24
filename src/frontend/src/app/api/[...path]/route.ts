import { proxyToBackend } from '../../../services/server/proxy';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export const GET = proxyToBackend;
export const POST = proxyToBackend;
export const PUT = proxyToBackend;
export const PATCH = proxyToBackend;
export const DELETE = proxyToBackend;
export const HEAD = proxyToBackend;
