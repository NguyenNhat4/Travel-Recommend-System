import { getSession } from '../../../../services/server/authRoutes';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export const GET = getSession;
