import type { Application } from 'express';
import type { SharedTripRecord, SharedTripStore } from '../stores/shared-trip-store';

export function registerTripRoutes(app: Application, sharedTripsStore: SharedTripStore) {
  app.post('/api/trips/share', async (req, res) => {
    try {
      const { plan, senderName, note } = req.body;
      if (!plan || !plan.title) {
        return res.status(400).json({ error: 'Dữ liệu lịch trình không hợp lệ' });
      }

      const dest = plan.intent?.destination || 'vietnam';
      const cleanDest = dest
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toLowerCase()
        .replace(/[^a-z0-9]/g, '-');
      const randomSuffix = Math.random().toString(36).substring(2, 7);
      const shareId = `vota-${cleanDest}-${randomSuffix}`;

      const tripItem: SharedTripRecord = {
        id: shareId,
        plan,
        senderName: senderName || 'Du khách X-OTA',
        note: note || '',
        createdAt: new Date().toISOString(),
        views: 1,
      };

      await sharedTripsStore.create(tripItem);
      return res.json({ success: true, shareId, trip: tripItem });
    } catch (err: any) {
      console.error('Error sharing trip:', err);
      return res.status(500).json({ error: 'Không thể tạo liên kết chia sẻ' });
    }
  });

  app.get('/api/trips/share/:shareId', async (req, res) => {
    const trip = await sharedTripsStore.getAndIncrementViews(req.params.shareId);
    if (!trip) {
      return res.status(404).json({ error: 'Không tìm thấy chuyến đi được chia sẻ' });
    }
    return res.json({ success: true, trip });
  });
}
