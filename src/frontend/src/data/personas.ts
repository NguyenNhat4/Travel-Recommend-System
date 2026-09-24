/**
 * V-OTA Seed Personas
 * Direct translation of spec:
 * P1: Minh Anh · Khách thân thiết (Nha Trang hotel booked -> cross_vertical to flight/attraction)
 * P2: Quốc Bảo · Mới tham gia (1-2 views -> coldStart: true, recent views)
 * P3: Thu Hà · Đã lâu không ghé (Dormant 6 months ago)
 * P4: Khách mới (0 events -> coldStart: true, popular)
 */

import { UserPersona } from '../types/travel';

export const SEED_PERSONAS: Record<string, UserPersona> = {
  P1: {
    id: 'P1',
    code: 'MA',
    name: 'Nguyễn Minh Anh',
    email: 'minhanh.nguyen@v-ota.demo',
    avatarText: 'MA',
    tagline: 'Khách thân thiết',
    description: 'Nhiều chuyến Nha Trang; có một chuyến sắp tới đã đặt khách sạn V-OTA Resort.',
    historySummary: 'Hay đi Nha Trang · Đã đặt khách sạn',
    coldStart: false,
    activeDestination: 'Nha Trang',
    bookedVerticals: ['hotel'],
    seedEvents: [
      {
        id: 'ev-p1-01',
        userId: 'P1',
        productId: 'nt-hotel-01',
        productName: 'V-OTA Resort Nha Trang - Deluxe Ocean View',
        eventType: 'purchase',
        taxonomy: 'hotel',
        destination: 'Nha Trang',
        timestamp: new Date(Date.now() - 3 * 24 * 3600 * 1000).toISOString(),
      },
      {
        id: 'ev-p1-02',
        userId: 'P1',
        productId: 'nt-attraction-01',
        productName: 'Vé Vui Chơi VinWonders Nha Trang (Cáp Treo Hai Chiều)',
        eventType: 'product_view',
        taxonomy: 'attraction',
        destination: 'Nha Trang',
        timestamp: new Date(Date.now() - 5 * 24 * 3600 * 1000).toISOString(),
      }
    ]
  },
  P2: {
    id: 'P2',
    code: 'QB',
    name: 'Trần Quốc Bảo',
    email: 'quocbao.tran@v-ota.demo',
    avatarText: 'QB',
    tagline: 'Mới tham gia',
    description: 'Mới xem 2 sản phẩm tại Nha Trang (V-OTA Resort và VinWonders).',
    historySummary: 'Mới xem 2 sản phẩm Nha Trang',
    coldStart: true,
    activeDestination: 'Nha Trang',
    bookedVerticals: [],
    seedEvents: [
      {
        id: 'ev-p2-01',
        userId: 'P2',
        productId: 'nt-hotel-01',
        productName: 'V-OTA Resort Nha Trang - Deluxe Ocean View',
        eventType: 'product_view',
        taxonomy: 'hotel',
        destination: 'Nha Trang',
        timestamp: new Date(Date.now() - 1 * 24 * 3600 * 1000).toISOString(),
      },
      {
        id: 'ev-p2-02',
        userId: 'P2',
        productId: 'nt-attraction-01',
        productName: 'Vé Vui Chơi VinWonders Nha Trang (Cáp Treo Hai Chiều)',
        eventType: 'product_view',
        taxonomy: 'attraction',
        destination: 'Nha Trang',
        timestamp: new Date(Date.now() - 2 * 3600 * 1000).toISOString(),
      }
    ]
  },
  P3: {
    id: 'P3',
    code: 'TH',
    name: 'Phạm Thu Hà',
    email: 'thuha.pham@v-ota.demo',
    avatarText: 'TH',
    tagline: 'Đã lâu không ghé',
    description: 'Chuyến gần nhất cách đây khoảng 6 tháng (đặt khách sạn & vé VinWonders).',
    historySummary: 'Chuyến cuối 6 tháng trước',
    coldStart: false,
    isDormant: true,
    activeDestination: 'Nha Trang',
    bookedVerticals: ['hotel', 'attraction'],
    seedEvents: [
      {
        id: 'ev-p3-01',
        userId: 'P3',
        productId: 'nt-hotel-01',
        productName: 'V-OTA Resort Nha Trang - Deluxe Ocean View',
        eventType: 'purchase',
        taxonomy: 'hotel',
        destination: 'Nha Trang',
        timestamp: new Date(Date.now() - 180 * 24 * 3600 * 1000).toISOString(),
      }
    ]
  },
  P4: {
    id: 'P4',
    code: 'KM',
    name: 'Khách mới',
    email: 'khachmoi@v-ota.demo',
    avatarText: 'KM',
    tagline: 'Chưa có lịch sử',
    description: 'Tài khoản hoàn toàn mới, 0 event. Hệ thống hiển thị danh mục phổ biến.',
    historySummary: 'Chưa có lịch sử',
    coldStart: true,
    activeDestination: undefined,
    bookedVerticals: [],
    seedEvents: []
  }
};

/**
 * Email đăng nhập thật của 4 persona seed (src/data_collection/seed/config.py PERSONAS) và
 * cdp_user_id tương ứng. `personaFromUser` dùng cdp_user_id để gắn thẻ persona sau khi đăng nhập qua `/login`.
 */
export const PERSONA_LOGIN: Record<string, { email: string; cdpUserId: string }> = {
  P1: { email: 'minh.anh@example.com', cdpUserId: 'VP0000001' },
  P2: { email: 'quoc.bao@example.com', cdpUserId: 'VP0000002' },
  P3: { email: 'thu.ha@example.com', cdpUserId: 'VP0000003' },
  P4: { email: 'khach.moi@example.com', cdpUserId: 'VP0000004' },
};
