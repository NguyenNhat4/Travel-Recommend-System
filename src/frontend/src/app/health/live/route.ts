// Liveness cho autohealing của nhóm VM: frontend còn sống và backend còn trả lời. Cố ý KHÔNG phụ thuộc RecSys
// hay database (khác /health/ready): nếu phụ thuộc thì Weaviate/DB gián đoạn làm autohealing thay VM liên tục
// mà không sửa được gì. Backend treo thì fetch hết hạn sau 3 giây và trả 503.
import { log } from '../../../lib/logger';

const backendBaseUrl = () => (process.env.BACKEND_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');

export async function GET() {
  try {
    const upstream = await fetch(`${backendBaseUrl()}/health`, {
      cache: 'no-store',
      signal: AbortSignal.timeout(3000),
    });
    log.debug('bff.health', { probe: 'live', status: upstream.status });
    return Response.json(
      { status: upstream.ok ? 'ok' : 'unavailable', live: upstream.ok },
      { status: upstream.ok ? 200 : 503, headers: { 'cache-control': 'no-store' } },
    );
  } catch (error) {
    log.warn('bff.health', { probe: 'live', outcome: 'backend_unreachable', error });
    return Response.json(
      { status: 'unavailable', live: false },
      { status: 503, headers: { 'cache-control': 'no-store' } },
    );
  }
}
