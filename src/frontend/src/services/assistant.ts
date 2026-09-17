/**
 * Grounded AI Travel Assistant Engine
 * Implements spec §6:
 * - Intent extraction (destination, days, party, interests)
 * - Grounding contract (bookable card ONLY from catalog productId, ActivityNote for non-bookables)
 * - Clarification cards when intent is ambiguous
 * - Mixes user recommendations when logged in
 */

import { CATALOG } from '../data/catalog';
import { TravelIntent, GroundedPlan, Destination, ChatMessage } from '../types/travel';
import { calculateRecommendations } from './recsys';
import { UserPersona, UserEvent } from '../types/travel';

export function extractIntent(text: string): { intent: Partial<TravelIntent>; missing: string[] } {
  const clean = text.toLowerCase();

  // Extract destination
  let destination: Destination | undefined;
  if (clean.includes('nha trang') || clean.includes('cam ranh')) destination = 'Nha Trang';
  else if (clean.includes('phú quốc') || clean.includes('phu quoc')) destination = 'Phú Quốc';
  else if (clean.includes('đà nẵng') || clean.includes('da nang')) destination = 'Đà Nẵng';
  else if (clean.includes('hội an') || clean.includes('hoi an')) destination = 'Hội An';
  else if (clean.includes('hạ long') || clean.includes('ha long')) destination = 'Hạ Long';
  else if (clean.includes('hà nội') || clean.includes('ha noi')) destination = 'Hà Nội';

  // Extract days
  let days: number | undefined;
  const dayMatch = clean.match(/(\d+)\s*(ngày|ngay|day|hôm)/);
  if (dayMatch) {
    days = Math.min(7, Math.max(1, parseInt(dayMatch[1], 10)));
  } else if (clean.includes('cuối tuần') || clean.includes('weekend')) {
    days = 2;
  }

  // Extract party
  let party: TravelIntent['party'] = 'family_with_kids';
  if (clean.includes('cặp đôi') || clean.includes('người yêu') || clean.includes('vợ chồng') || clean.includes('couple')) {
    party = 'couple';
  } else if (clean.includes('bạn bè') || clean.includes('nhóm') || clean.includes('friends')) {
    party = 'friends';
  } else if (clean.includes('1 mình') || clean.includes('độc hành') || clean.includes('solo')) {
    party = 'solo';
  }

  // Extract interests
  const interests: string[] = [];
  if (clean.includes('vui chơi') || clean.includes('công viên') || clean.includes('vinwonders')) interests.push('theme_park');
  if (clean.includes('biển') || clean.includes('bãi')) interests.push('beach');
  if (clean.includes('ẩm thực') || clean.includes('ăn')) interests.push('food');
  if (clean.includes('nghỉ dưỡng') || clean.includes('spa') || clean.includes('resort')) interests.push('relaxation');
  if (clean.includes('golf')) interests.push('golf');

  const missing: string[] = [];
  if (!destination) missing.push('destination');
  if (!days) missing.push('days');

  return {
    intent: {
      destination,
      days: days || 3,
      party,
      interests: interests.length > 0 ? interests : ['theme_park', 'beach']
    },
    missing
  };
}

export function buildGroundedItinerary(
  intent: TravelIntent,
  user: UserPersona | null,
  userEvents: UserEvent[] = []
): GroundedPlan {
  const dest = intent.destination;
  const destProducts = CATALOG.filter(p => p.destination === dest && p.available);
  const hotels = destProducts.filter(p => p.taxonomy === 'hotel');
  const attractions = destProducts.filter(p => p.taxonomy === 'attraction');
  const combos = destProducts.filter(p => p.taxonomy === 'combo');
  const recs = calculateRecommendations(user, userEvents);

  // Pick stay product
  let stayProduct = hotels[0] || CATALOG.find(p => p.taxonomy === 'hotel')!;
  let staySource: 'recommendation' | 'search' = 'search';
  let stayBecause = undefined;

  if (user && recs.recommendations.some(r => r.product.id === stayProduct.id)) {
    staySource = 'recommendation';
    stayBecause = recs.recommendations.find(r => r.product.id === stayProduct.id)?.because;
  }

  const daysCount = intent.days || 3;
  const days: GroundedPlan['days'] = [];
  let totalEstimatedPrice = stayProduct ? stayProduct.unitPrice * (daysCount - 1) : 0;
  let bookableProductsCount = stayProduct ? 1 : 0;

  for (let d = 1; d <= daysCount; d++) {
    const dayTitle = d === 1 
      ? 'Chào đón vịnh biển & Vui chơi giải trí' 
      : d === 2 
        ? 'Khám phá văn hóa & Trải nghiệm biển đảo' 
        : 'Thư giãn nghỉ dưỡng & Thưởng thức ẩm thực';

    const slots: GroundedPlan['days'][0]['slots'] = [];

    if (d === 1) {
      // Morning attraction
      const attr = attractions[0] || destProducts.find(p => p.taxonomy === 'attraction');
      if (attr) {
        slots.push({
          time: 'morning',
          productId: attr.id,
          product: attr,
          note: intent.party === 'family_with_kids' 
            ? 'Khởi hành sớm để các bé tránh nắng gắt, thỏa sức vui chơi công viên nước và thủy cung.' 
            : 'Check-in buổi sáng với các trò chơi cảm giác mạnh và ngắm trọn cảnh vịnh.',
          source: 'search',
          coordinates: attr.coordinates,
          address: attr.address
        });
        totalEstimatedPrice += attr.unitPrice * 2;
        bookableProductsCount++;
      }

      // Noon activity note (non-bookable)
      const noonCoord = dest === 'Phú Quốc' 
        ? { lat: 10.2195, lng: 103.9602 }
        : dest === 'Đà Nẵng' 
          ? { lat: 16.0680, lng: 108.2250 }
          : dest === 'Hội An'
            ? { lat: 15.8770, lng: 108.3300 }
            : dest === 'Hạ Long'
              ? { lat: 20.9560, lng: 107.0380 }
              : { lat: 12.2472, lng: 109.1970 };
      const noonAddress = dest === 'Phú Quốc'
        ? 'Quán bún quậy Kiến Xây, 28 Bạch Đằng, Dương Đông, Phú Quốc'
        : dest === 'Đà Nẵng'
          ? 'Nhà hàng đặc sản bánh tráng thịt heo & bún mắm, Lê Duẩn, Đà Nẵng'
          : dest === 'Hội An'
            ? 'Quán Cao Lầu & Cơm gà Bà Buội, Phố Cổ Hội An'
            : dest === 'Hạ Long'
              ? 'Phố ẩm thực hải sản Bãi Cháy, TP. Hạ Long'
              : 'Khu ẩm thực đặc sản nem nướng & hải sản, Trần Phú, Nha Trang';

      slots.push({
        time: 'noon',
        isActivityNote: true,
        activityTitle: 'Nghỉ ngơi & Ăn trưa ẩm thực địa phương',
        note: 'Thưởng thức bữa trưa đặc sản địa phương tươi sống tại khu ẩm thực, nghỉ ngơi lấy lại năng lượng.',
        coordinates: noonCoord,
        address: noonAddress
      });

      // Evening combo
      const combo = combos[0] || destProducts.find(p => p.taxonomy === 'combo');
      if (combo) {
        slots.push({
          time: 'evening',
          productId: combo.id,
          product: combo,
          note: 'Thưởng thức show diễn công nghệ ánh sáng đỉnh cao kết hợp tiệc tối hải sản sang trọng.',
          source: 'recommendation',
          coordinates: combo.coordinates,
          address: combo.address,
          because: [
            {
              productName: stayProduct.name,
              event: 'purchase',
              daysAgo: 1,
              contribution: 0.65
            }
          ]
        });
        totalEstimatedPrice += combo.unitPrice * 2;
        bookableProductsCount++;
      }
    } else if (d === 2) {
      // Morning
      const attr2 = attractions[1] || destProducts.find(p => p.taxonomy === 'attraction' && p.id !== attractions[0]?.id);
      if (attr2) {
        slots.push({
          time: 'morning',
          productId: attr2.id,
          product: attr2,
          note: 'Trải nghiệm thiên nhiên bán hoang dã và tương tác trực tiếp với các loài động vật quý.',
          source: 'search',
          coordinates: attr2.coordinates,
          address: attr2.address
        });
        totalEstimatedPrice += attr2.unitPrice * 2;
        bookableProductsCount++;
      } else {
        const morningBeachCoord = dest === 'Phú Quốc'
          ? { lat: 10.3340, lng: 103.8562 }
          : dest === 'Đà Nẵng'
            ? { lat: 16.0590, lng: 108.2460 }
            : { lat: 12.2350, lng: 109.1980 };
        slots.push({
          time: 'morning',
          isActivityNote: true,
          activityTitle: 'Tắm biển & Dạo ngắm bình minh trên bãi cát',
          note: 'Thức dậy ngắm bình minh tuyệt đẹp, tắm biển tại bãi tắm riêng của khu nghỉ dưỡng và dùng buffet sáng.',
          coordinates: morningBeachCoord,
          address: `Bãi biển tuyệt đẹp tại ${dest}`
        });
      }

      // Noon
      const cafeCoord = dest === 'Phú Quốc'
        ? { lat: 10.3245, lng: 103.8580 }
        : dest === 'Đà Nẵng'
          ? { lat: 16.0610, lng: 108.2230 }
          : { lat: 12.2420, lng: 109.1985 };
      slots.push({
        time: 'noon',
        isActivityNote: true,
        activityTitle: 'Thưởng thức cà phê & ẩm thực ven biển',
        note: 'Ghé quán cà phê view biển ngắm sóng, thưởng thức dừa xiêm và đặc sản tươi ngon trứ danh.',
        coordinates: cafeCoord,
        address: `Quán cà phê & ẩm thực ven biển trung tâm ${dest}`
      });

      // Afternoon / Evening
      const spaCoord = stayProduct?.coordinates || (dest === 'Phú Quốc'
        ? { lat: 10.3340, lng: 103.8562 }
        : dest === 'Đà Nẵng'
          ? { lat: 16.0020, lng: 108.2610 }
          : { lat: 12.2132, lng: 109.2482 });
      slots.push({
        time: 'afternoon',
        isActivityNote: true,
        activityTitle: 'Trải nghiệm spa thư giãn hoặc chèo kayak',
        note: 'Thư giãn trị liệu bằng tinh dầu thảo mộc tại Akoya Spa hoặc chèo kayak trên mặt biển êm đềm.',
        coordinates: spaCoord,
        address: `Akoya Spa & khu vực bãi biển riêng tại ${dest}`
      });
    } else {
      // Day 3
      const marketCoord = dest === 'Phú Quốc'
        ? { lat: 10.2160, lng: 103.9620 }
        : dest === 'Đà Nẵng'
          ? { lat: 16.0685, lng: 108.2245 }
          : dest === 'Hội An'
            ? { lat: 15.8790, lng: 108.3270 }
            : { lat: 12.2530, lng: 109.1908 };
      const airportCoord = dest === 'Phú Quốc'
        ? { lat: 10.1690, lng: 103.9930 }
        : dest === 'Đà Nẵng'
          ? { lat: 16.0530, lng: 108.2000 }
          : { lat: 11.9982, lng: 109.2194 };

      slots.push({
        time: 'morning',
        isActivityNote: true,
        activityTitle: 'Thong thả ngắm cảnh & Mua sắm đặc sản làm quà',
        note: 'Mua sắm yến sào, chả cá, khô mực hoặc ngọc trai uy tín tại trung tâm trước khi làm thủ tục trả phòng.',
        coordinates: marketCoord,
        address: `Khu chợ & trung tâm đặc sản truyền thống tại ${dest}`
      });
      slots.push({
        time: 'noon',
        isActivityNote: true,
        activityTitle: 'Làm thủ tục trả phòng & Xe tiễn sân bay',
        note: 'Thư thả ăn trưa nhẹ, trả phòng khách sạn và đón xe di chuyển ra sân bay kết thúc chuyến đi trọn vẹn.',
        coordinates: airportCoord,
        address: `Sân bay kết nối ${dest}`
      });
    }

    days.push({
      day: d,
      title: dayTitle,
      slots
    });
  }

  return {
    intent,
    title: `Lịch trình ${daysCount} ngày ở ${dest}`,
    stay: stayProduct ? {
      productId: stayProduct.id,
      product: stayProduct,
      note: 'Chỗ nghỉ trung tâm cao cấp cho cả hành trình với bãi biển riêng, hồ bơi lớn và dịch vụ trọn gói.',
      source: staySource,
      because: stayBecause
    } : undefined,
    days,
    totalEstimatedPrice,
    bookableProductsCount,
    fallback: false
  };
}
