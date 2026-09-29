import type { Product, ItinerarySlot } from '../../../types/travel';

interface HotelVisualData {
  tags: { label: string; icon: string }[];
  images: { url: string; caption: string }[];
  isVilla: boolean;
}

/**
 * Trích xuất điểm HOT (Nha Trang, Biệt thự, Hồ bơi...) và 2 hình ảnh to rõ cho Khách sạn lưu trú
 */
export const getHotelVisuals = (product: Product, destination: string): HotelVisualData => {
  const tags: { label: string; icon: string }[] = [];
  tags.push({ label: destination, icon: '📍' });

  const isVilla = product.name.toLowerCase().includes('biệt thự') ||
    product.id.includes('hotel-02');

  if (isVilla) {
    tags.push({ label: 'Biệt thự sang trọng', icon: '🏡' });
  } else {
    tags.push({ label: 'Resort 5★ biển', icon: '🏨' });
  }

  const hasPool = product.name.toLowerCase().includes('hồ bơi') ||
    product.attributes?.pool;

  if (hasPool) {
    tags.push({
      label: isVilla ? 'Hồ bơi riêng' : 'Hồ bơi lớn',
      icon: '🏊‍♂️'
    });
  }

  if (product.attributes?.oceanView || product.attributes?.privateBeach) {
    tags.push({ label: 'View biển', icon: '🌊' });
  }

  // Khớp ảnh chuẩn xác theo từng khách sạn và đặc trưng
  let img1 = product.imageUrl;
  let img2 = 'https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?auto=format&fit=crop&w=1200&q=80';

  if (product.id === 'nt-hotel-02') {
    // Biệt thự hồ bơi riêng Nha Trang: Biệt thự sang trọng & Hồ bơi riêng villa
    img1 = 'https://images.unsplash.com/photo-1582719508461-905c673771fd?auto=format&fit=crop&w=1200&q=80';
    img2 = 'https://images.unsplash.com/photo-1540555700478-4be289fbecef?auto=format&fit=crop&w=1200&q=80';
  } else if (product.id === 'nt-hotel-01') {
    // Deluxe Ocean View Nha Trang: Phòng nghỉ view biển & Hồ bơi lớn Hòn Tre
    img1 = 'https://images.unsplash.com/photo-1590490360182-c33d57733427?auto=format&fit=crop&w=1200&q=80';
    img2 = 'https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?auto=format&fit=crop&w=1200&q=80';
  } else if (product.id === 'pq-hotel-02') {
    // Wonder World Biệt thự biển Phú Quốc
    img1 = 'https://images.unsplash.com/photo-1618773928121-c32242e63f39?auto=format&fit=crop&w=1200&q=80';
    img2 = 'https://images.unsplash.com/photo-1540555700478-4be289fbecef?auto=format&fit=crop&w=1200&q=80';
  } else if (product.id === 'pq-hotel-01') {
    // Resort & Spa Bãi Dài Phú Quốc
    img1 = 'https://images.unsplash.com/photo-1590490360182-c33d57733427?auto=format&fit=crop&w=1200&q=80';
    img2 = 'https://images.unsplash.com/photo-1571896349842-33c89424de2d?auto=format&fit=crop&w=1200&q=80';
  } else if (product.id === 'dn-hotel-01') {
    // Biệt thự Non Nước Đà Nẵng
    img1 = 'https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=1200&q=80';
    img2 = 'https://images.unsplash.com/photo-1520250497591-112f2f40a3f4?auto=format&fit=crop&w=1200&q=80';
  } else if (isVilla) {
    img1 = 'https://images.unsplash.com/photo-1582719508461-905c673771fd?auto=format&fit=crop&w=1200&q=80';
    img2 = 'https://images.unsplash.com/photo-1540555700478-4be289fbecef?auto=format&fit=crop&w=1200&q=80';
  } else {
    img1 = product.imageUrl || 'https://images.unsplash.com/photo-1590490360182-c33d57733427?auto=format&fit=crop&w=1200&q=80';
    img2 = 'https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?auto=format&fit=crop&w=1200&q=80';
  }

  return {
    tags: tags.slice(0, 4),
    images: [
      { url: img1, caption: isVilla ? '🏡 Không gian biệt thự nghỉ dưỡng' : '🏨 Phòng nghỉ tiện nghi 5 sao' },
      { url: img2, caption: hasPool ? (isVilla ? '🏊‍♂️ Hồ bơi riêng & sân vườn' : '🏊‍♂️ Hồ bơi lớn & vịnh biển') : '🌊 Vịnh biển riêng tư' }
    ],
    isVilla
  };
};

/**
 * Trích xuất ảnh to rõ ĐÚNG 100% NỘI DUNG cho từng chặng hoạt động trong lộ trình
 */
export const getSlotVisualUrl = (slot: ItinerarySlot, destination: string): string => {
  const title = (slot.activityTitle || '').toLowerCase();
  const note = (slot.note || '').toLowerCase();
  const name = (slot.product?.name || '').toLowerCase();
  const loc = (slot.locationName || '').toLowerCase();
  const text = `${title} ${note} ${name} ${loc}`;

  // 1. Show diễn nghệ thuật / Tata Show / Ánh sáng 3D mapping / Nhạc nước
  if (text.includes('tata show') || text.includes('show') || text.includes('mapping') || text.includes('nhạc nước') || text.includes('biểu diễn nghệ thuật')) {
    return 'https://images.unsplash.com/photo-1514525253161-7a46d19cd819?auto=format&fit=crop&w=1200&q=80';
  }

  // 2. Akoya Spa thư giãn / Massage trị liệu tinh dầu
  if (text.includes('spa') || text.includes('massage') || text.includes('thư giãn') || text.includes('trị liệu') || text.includes('akoya')) {
    return 'https://images.unsplash.com/photo-1544161515-4ab6ce6db874?auto=format&fit=crop&w=1200&q=80';
  }

  // 3. Quán Cà phê ven biển / Ngắm sóng / Nước dừa xiêm / Trà chiều
  if (text.includes('cà phê') || text.includes('cafe') || text.includes('ngắm sóng') || text.includes('trà chiều')) {
    return 'https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?auto=format&fit=crop&w=1200&q=80';
  }

  // 4. Chèo kayak / Lặn biển / Ngắm san hô
  if (text.includes('kayak') || text.includes('chèo') || text.includes('lặn') || text.includes('san hô')) {
    return 'https://images.unsplash.com/photo-1544551763-46a013bb70d5?auto=format&fit=crop&w=1200&q=80';
  }

  // 5. Chợ đặc sản / Mua sắm quà lưu niệm (chợ Đầm, chợ Hàn, yến sào, ngọc trai...)
  if (text.includes('chợ') || text.includes('mua sắm') || text.includes('làm quà') || text.includes('quà lưu niệm') || text.includes('đặc sản làm quà')) {
    return 'https://images.unsplash.com/photo-1533900298318-6b8da08a523e?auto=format&fit=crop&w=1200&q=80';
  }

  // 6. Làm thủ tục trả phòng & Xe tiễn sân bay / Chuyến bay
  if (text.includes('sân bay') || text.includes('tiễn sân bay') || text.includes('trả phòng') || text.includes('đón xe')) {
    return 'https://images.unsplash.com/photo-1436491865332-7a61a109cc05?auto=format&fit=crop&w=1200&q=80';
  }

  // 7. Bãi biển / Tắm biển / Dạo bình minh trên cát / Hoàng hôn
  if (text.includes('bình minh') || text.includes('tắm biển') || text.includes('bãi biển') || text.includes('dạo biển') || text.includes('bãi cát')) {
    return 'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1200&q=80';
  }

  // 8. Ẩm thực địa phương / Ăn trưa / Bún quậy / Nem nướng / Bánh tráng thịt heo / Cao lầu / Hải sản
  if (text.includes('ẩm thực') || text.includes('ăn trưa') || text.includes('buffet') || text.includes('nem nướng') || text.includes('bún quậy') || text.includes('cao lầu') || text.includes('hải sản')) {
    return 'https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=1200&q=80';
  }

  // 9. Safari / River Safari / Động vật bán hoang dã
  if (text.includes('safari') || text.includes('vườn thú') || text.includes('động vật')) {
    return 'https://images.unsplash.com/photo-1534177616072-ef7dc120449d?auto=format&fit=crop&w=1200&q=80';
  }

  // 10. Bà Nà Hills / Cầu Vàng
  if (text.includes('cầu vàng') || text.includes('bà nà') || text.includes('bana')) {
    return 'https://images.unsplash.com/photo-1559592413-7cec4d0cae2b?auto=format&fit=crop&w=1200&q=80';
  }

  // 10b. Đà Lạt: thác, đồi chè, hoa và núi rừng
  if (text.includes('datanla') || text.includes('thác voi') || text.includes('thác nước')) {
    return 'https://images.unsplash.com/photo-1433086966358-54859d0ed716?auto=format&fit=crop&w=1200&q=80';
  }
  if (text.includes('đồi chè') || text.includes('săn mây') || text.includes('cầu đất')) {
    return 'https://images.unsplash.com/photo-1594631252845-29fc4cc8cde9?auto=format&fit=crop&w=1200&q=80';
  }
  if (text.includes('langbiang') || text.includes('đồi thông') || text.includes('cao nguyên')) {
    return 'https://images.unsplash.com/photo-1583417319070-4a69db38a482?auto=format&fit=crop&w=1200&q=80';
  }
  if (text.includes('vườn hoa') || text.includes('hoa theo mùa') || text.includes('trại mát')) {
    return 'https://images.unsplash.com/photo-1490750967868-88aa4486c946?auto=format&fit=crop&w=1200&q=80';
  }

  // 11. Sân Golf
  if (text.includes('golf') || text.includes('hố')) {
    return 'https://images.unsplash.com/photo-1535131749006-b7f58c99034b?auto=format&fit=crop&w=1200&q=80';
  }

  // 12. Nếu slot gắn liền với sản phẩm có ảnh đại diện sẵn trong catalog
  if (slot.product?.imageUrl) {
    return slot.product.imageUrl;
  }

  // 13. VinWonders / Công viên vui chơi / Cáp treo
  if (text.includes('vinwonders') || text.includes('công viên') || text.includes('cáp treo') || text.includes('vui chơi')) {
    return 'https://images.unsplash.com/photo-1513889961551-628c1e5e2ee9?auto=format&fit=crop&w=1200&q=80';
  }

  // Fallback theo điểm đến
  if (destination === 'Phú Quốc') {
    return 'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1200&q=80';
  }
  if (destination === 'Đà Nẵng' || destination === 'Hội An') {
    return 'https://images.unsplash.com/photo-1552465011-b4e21bf6e79a?auto=format&fit=crop&w=1200&q=80';
  }
  if (destination === 'Đà Lạt') {
    return 'https://images.unsplash.com/photo-1578637387939-43c525550085?auto=format&fit=crop&w=1200&q=80';
  }
  return 'https://images.unsplash.com/photo-1513889961551-628c1e5e2ee9?auto=format&fit=crop&w=1200&q=80';
};
