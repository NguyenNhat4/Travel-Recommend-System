/**
 * Grounded AI Travel Assistant Engine
 * Implements spec §6:
 * - Intent extraction (destination, days, party, interests)
 * - Grounding contract (bookable card ONLY from catalog productId, ActivityNote for non-bookables)
 * - Clarification cards when intent is ambiguous
 * - Mixes user recommendations when logged in
 */

import { CATALOG } from '../data/catalog';
import { TravelIntent, GroundedPlan, Destination, ChatMessage, ItinerarySlot, ItineraryDay, Product } from '../types/travel';
import { calculateRecommendations } from './recsys';
import { UserPersona, UserEvent } from '../types/travel';
import { detectTransitMode } from './routeGeometry';
import type { components } from '../types/api.gen';

export function extractIntent(text: string): { intent: Partial<TravelIntent>; missing: string[] } {
  const clean = text.toLowerCase();

  // Extract destination
  let destination: Destination | undefined;
  if (clean.includes('nha trang') || clean.includes('cam ranh')) destination = 'Nha Trang';
  else if (clean.includes('phú quốc') || clean.includes('phu quoc')) destination = 'Phú Quốc';
  else if (clean.includes('đà nẵng') || clean.includes('da nang')) destination = 'Đà Nẵng';
  else if (clean.includes('đà lạt') || clean.includes('da lat')) destination = 'Đà Lạt';
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
  if (clean.includes('biệt thự') || clean.includes('villa')) interests.push('villa');
  if (clean.includes('hồ bơi') || clean.includes('bể bơi') || clean.includes('pool')) interests.push('pool');

  const missing: string[] = [];
  if (!destination) missing.push('destination');
  if (!days) missing.push('days');

  const isMultiHotel = clean.includes('2 khách sạn') || 
    clean.includes('hai khách sạn') || 
    clean.includes('2 resort') || 
    clean.includes('hai resort') || 
    clean.includes('đổi khách sạn') || 
    clean.includes('nhiều khách sạn') || 
    clean.includes('split stay');

  return {
    intent: {
      destination,
      days: days || 3,
      party,
      interests: interests.length > 0 ? interests : ['theme_park', 'beach'],
      multiHotel: isMultiHotel
    },
    missing
  };
}

const DALAT_TIME_RANGES: Record<ItinerarySlot['time'], string> = {
  morning: '08:00 - 11:30',
  noon: '11:45 - 13:30',
  afternoon: '14:30 - 17:30',
  evening: '18:00 - 21:00',
};

const makeDalatProductSlot = (
  time: ItinerarySlot['time'],
  product: Product,
  note: string,
  transitInfo: string,
  transitMode: ItinerarySlot['transitMode'] = 'driving'
): ItinerarySlot => ({
  time,
  timeRange: DALAT_TIME_RANGES[time],
  activityTitle: product.name,
  locationName: product.name,
  productId: product.id,
  product,
  note,
  source: 'curated',
  coordinates: product.coordinates,
  address: product.address,
  transitInfo,
  transitMode,
});

const makeDalatActivityNote = (
  time: ItinerarySlot['time'],
  activityTitle: string,
  locationName: string,
  note: string,
  coordinates: { lat: number; lng: number },
  address: string,
  transitInfo: string,
  transitMode: ItinerarySlot['transitMode'] = 'driving'
): ItinerarySlot => ({
  time,
  timeRange: DALAT_TIME_RANGES[time],
  isActivityNote: true,
  activityTitle,
  locationName,
  note,
  source: 'curated',
  coordinates,
  address,
  transitInfo,
  transitMode,
});

function buildDalatItinerary(
  intent: TravelIntent,
  user: UserPersona | null,
  userEvents: UserEvent[]
): GroundedPlan {
  const dalatProducts = CATALOG.filter(p => p.destination === 'Đà Lạt' && p.available);
  const hotels = dalatProducts.filter(p => p.taxonomy === 'hotel');
  const product = (id: string) => dalatProducts.find(p => p.id === id)!;
  const recs = calculateRecommendations(user, userEvents);
  const daysCount = Math.min(7, Math.max(1, intent.days || 7));
  const isMultiHotel = Boolean(intent.multiHotel && hotels.length >= 2);
  const primaryStayProduct = hotels.find(h => intent.interests?.some(i => i === 'villa' || i === 'pool') && h.attributes?.pool)
    || hotels[0];

  const recommendationFor = (hotel: Product) => {
    const match = user && recs.recommendations.find(r => r.product.id === hotel.id);
    return {
      source: match ? 'recommendation' as const : 'search' as const,
      because: match?.because,
    };
  };

  let stay: GroundedPlan['stay'];
  let stays: GroundedPlan['stays'];
  let totalEstimatedPrice = 0;
  let bookableProductsCount = 0;

  if (isMultiHotel) {
    const totalNights = Math.max(2, daysCount - 1);
    const nights1 = Math.ceil(totalNights / 2);
    const nights2 = totalNights - nights1;
    const hotel1 = hotels[0];
    const hotel2 = hotels[1];
    const hotel1Recommendation = recommendationFor(hotel1);
    const hotel2Recommendation = recommendationFor(hotel2);

    stays = [
      {
        productId: hotel1.id,
        product: hotel1,
        nights: nights1,
        dayRange: `Chặng 1: Đêm 1 - ${nights1} (Ngày 1 - ${nights1 + 1})`,
        note: `Nghỉ ${nights1} đêm đầu giữa đồi thông tại ${hotel1.name}.`,
        ...hotel1Recommendation,
      },
      {
        productId: hotel2.id,
        product: hotel2,
        nights: nights2,
        dayRange: `Chặng 2: Đêm ${nights1 + 1} - ${totalNights} (Ngày ${nights1 + 1} - ${daysCount})`,
        note: `Đổi không gian sang villa sân vườn tại ${hotel2.name} cho những ngày cuối hành trình.`,
        ...hotel2Recommendation,
      },
    ];
    totalEstimatedPrice += hotel1.unitPrice * nights1 + hotel2.unitPrice * nights2;
    bookableProductsCount += 2;
  } else if (primaryStayProduct) {
    const stayRecommendation = recommendationFor(primaryStayProduct);
    stay = {
      productId: primaryStayProduct.id,
      product: primaryStayProduct,
      note: `Lưu trú giữa đồi thông tại ${primaryStayProduct.name}, thuận tiện đi cả trung tâm lẫn các cung đường ngoại ô.`,
      ...stayRecommendation,
    };
    totalEstimatedPrice += primaryStayProduct.unitPrice * Math.max(1, daysCount - 1);
    bookableProductsCount += 1;
  }

  const dayDefinitions: Array<{ title: string; slots: ItinerarySlot[] }> = [
    {
      title: 'Khởi hành từ TP.HCM lên Đà Lạt & Làm quen phố núi',
      slots: [
        makeDalatActivityNote('morning', 'Khởi hành từ TP. Hồ Chí Minh đi Đà Lạt', 'Bến xe Liên tỉnh Đà Lạt (Đầu Đèo Prenn)', 'Khởi hành sáng sớm từ TP.HCM theo cao tốc và QL20, vượt cung đèo Prenn cửa ngõ để tiến vào thành phố hoa.', { lat: 11.9287, lng: 108.4447 }, 'Đầu Đèo Prenn, Phường 3, TP. Đà Lạt', 'Di chuyển xe ô tô/limousine từ TP.HCM qua Đèo Prenn vào trung tâm Đà Lạt.', 'driving'),
        makeDalatActivityNote('noon', 'Nhận phòng & Bữa trưa đặc sản phố núi', 'Khu ẩm thực trung tâm Đà Lạt', 'Check-in khách sạn, nghỉ ngơi và thưởng thức bánh căn, nem nướng hoặc lẩu gà lá é ấm cúng.', { lat: 11.9401, lng: 108.4371 }, 'Khu ẩm thực trung tâm, Phường 1, TP. Đà Lạt', 'Lái xe khoảng 10 - 15 phút từ nơi lưu trú về khu ẩm thực trung tâm.', 'driving'),
        makeDalatProductSlot('afternoon', product('dl-attraction-01'), 'Bắt đầu nhẹ nhàng bằng cung đi bộ quanh hồ Xuân Hương và quảng trường Lâm Viên; phù hợp để làm quen độ cao và nhịp phố.', 'Đi bộ khoảng 10 - 20 phút giữa hồ, quảng trường và khu trung tâm.', 'walking'),
        makeDalatProductSlot('evening', product('dl-combo-02'), 'Dạo chợ đêm, thử món nóng và kết thúc ngày đầu bằng một vòng quanh khu Hòa Bình.', 'Đi bộ khoảng 10 phút từ khu trung tâm đến chợ đêm.', 'walking'),
      ],
    },
    {
      title: 'Rừng thông, thác nước & hồ Tuyền Lâm',
      slots: [
        makeDalatProductSlot('morning', product('dl-attraction-02'), 'Khám phá thác Datanla, đi bộ trong rừng thông và trải nghiệm máng trượt theo nhịp phù hợp.', 'Lái xe khoảng 25 phút từ trung tâm theo hướng đèo Prenn.', 'driving'),
        makeDalatActivityNote('noon', 'Nghỉ trưa bên hồ Tuyền Lâm', 'Hồ Tuyền Lâm', 'Dùng bữa trưa giữa không gian hồ và rừng thông; nên dành thời gian nghỉ trước buổi chiều thư giãn.', { lat: 11.8966, lng: 108.4359 }, 'Khu hồ Tuyền Lâm, Phường 4, TP. Đà Lạt', 'Lái xe khoảng 10 phút từ Datanla đến hồ Tuyền Lâm.', 'driving'),
        makeDalatActivityNote('afternoon', 'Spa & trà chiều giữa đồi thông', 'Khu nghỉ dưỡng Đà Lạt', 'Thả lỏng với spa, hồ bơi nước ấm hoặc trà chiều tại nơi lưu trú để cân bằng sau ngày vận động.', primaryStayProduct?.coordinates || { lat: 11.9465, lng: 108.4415 }, primaryStayProduct?.address || 'Khu nghỉ dưỡng Đà Lạt', 'Lái xe khoảng 20 phút về nơi lưu trú.', 'driving'),
      ],
    },
    {
      title: 'Langbiang & sắc xanh cao nguyên',
      slots: [
        makeDalatProductSlot('morning', product('dl-attraction-03'), 'Đi về phía Bắc thành phố, ngắm rừng thông và toàn cảnh cao nguyên từ Langbiang.', 'Lái xe khoảng 35 phút từ trung tâm Đà Lạt.', 'driving'),
        makeDalatActivityNote('noon', 'Cơm gà & cà phê Lạc Dương', 'Thị trấn Lạc Dương', 'Ăn trưa với món địa phương, sau đó nghỉ ngắn trong quán cà phê nhìn ra đồi núi.', { lat: 12.0065, lng: 108.4412 }, 'Thị trấn Lạc Dương, Lâm Đồng', 'Lái xe khoảng 10 phút từ Langbiang vào khu dân cư địa phương.', 'driving'),
        makeDalatActivityNote('evening', 'Hoàng hôn và tối tự do', 'Hồ Xuân Hương', 'Về lại trung tâm, dạo hồ lúc hoàng hôn và tự do chọn quán ăn theo sở thích.', { lat: 11.9416, lng: 108.4382 }, 'Hồ Xuân Hương, Phường 1, TP. Đà Lạt', 'Lái xe khoảng 35 phút về trung tâm.', 'driving'),
      ],
    },
    {
      title: 'Săn mây và đồi chè Cầu Đất',
      slots: [
        makeDalatProductSlot('morning', product('dl-attraction-04'), 'Khởi hành sớm để săn mây, đi giữa những luống chè và ghé nông trại vùng Xuân Trường.', 'Lái xe khoảng 45 - 60 phút từ trung tâm theo cung Trại Mát - Cầu Đất.', 'driving'),
        makeDalatActivityNote('noon', 'Bữa trưa farm-to-table', 'Nông trại Xuân Trường', 'Thưởng thức rau củ tươi, gà đồi hoặc món nóng địa phương tại nông trại; đặt trước nếu đi nhóm đông.', { lat: 11.8215, lng: 108.5202 }, 'Xã Xuân Trường, TP. Đà Lạt, Lâm Đồng', 'Di chuyển khoảng 10 phút từ đồi chè đến nông trại gần đó.', 'driving'),
        makeDalatActivityNote('afternoon', 'Thử vị cà phê cao nguyên', 'Quán cà phê đồi chè Cầu Đất', 'Chọn một quán có sân hiên nhìn đồi chè, nghỉ ngơi và về lại thành phố trước giờ tối.', { lat: 11.8120, lng: 108.5265 }, 'Cung Cầu Đất, TP. Đà Lạt, Lâm Đồng', 'Lái xe khoảng 10 phút trong cung Cầu Đất, sau đó quay về trung tâm.', 'driving'),
      ],
    },
    {
      title: 'Kiến trúc cổ, Trại Mát & vườn hoa',
      slots: [
        makeDalatProductSlot('morning', product('dl-attraction-05'), 'Tham quan ga Đà Lạt, đi tuyến Trại Mát và ghé chùa Linh Phước để đổi nhịp sau ngày đi xa.', 'Lái xe khoảng 15 phút từ trung tâm đến ga Đà Lạt và Trại Mát.', 'driving'),
        makeDalatProductSlot('afternoon', product('dl-attraction-06'), 'Dành buổi chiều chụp ảnh hoa theo mùa, đi bộ thư thả bên hồ Xuân Hương.', 'Lái xe khoảng 15 phút từ Trại Mát về vườn hoa thành phố.', 'driving'),
        makeDalatProductSlot('evening', product('dl-combo-02'), 'Ăn tối nhẹ và quay lại chợ đêm nếu muốn mua đặc sản, quà lưu niệm cho gia đình.', 'Đi bộ khoảng 10 phút trong khu trung tâm.', 'walking'),
      ],
    },
    {
      title: 'Tà Nung, farm và cà phê địa phương',
      slots: [
        makeDalatProductSlot('morning', product('dl-combo-01'), 'Dành trọn ngày trên cung Tà Nung, kết hợp farm cà phê, thác Voi và những đoạn đường đồi xanh.', 'Lái xe khoảng 35 - 45 phút từ trung tâm theo hướng Tà Nung.', 'driving'),
        makeDalatActivityNote('noon', 'Bữa trưa tại farm', 'Farm cà phê Tà Nung', 'Tìm hiểu quy trình sơ chế cà phê và dùng bữa trưa đơn giản giữa vườn cây.', { lat: 11.8155, lng: 108.2860 }, 'Cung đường Tà Nung, Lâm Hà, Lâm Đồng', 'Di chuyển khoảng 10 phút trong cung Tà Nung.', 'driving'),
        makeDalatActivityNote('afternoon', 'Ngắm hoàng hôn trên đồi', 'Cung đường đồi Tà Nung', 'Về chậm qua cung đồi, dừng ở điểm nhìn an toàn để ngắm hoàng hôn trước khi về thành phố.', { lat: 11.8460, lng: 108.3250 }, 'Cung Tà Nung, Lâm Đồng', 'Lái xe khoảng 20 phút từ farm đến điểm ngắm cảnh, sau đó quay về nơi lưu trú.', 'driving'),
      ],
    },
    {
      title: 'Cà phê sáng, mua quà & Khởi hành về lại TP.HCM',
      slots: [
        makeDalatActivityNote('morning', 'Cà phê sáng & Dạo phố thong thả', 'Khu Hòa Bình', 'Dành buổi sáng thong thả để ăn brunch, mua cà phê rang xay và kiểm tra lại hành lý.', { lat: 11.9408, lng: 108.4373 }, 'Khu Hòa Bình, Phường 1, TP. Đà Lạt', 'Đi bộ hoặc đạp xe nhẹ trong khu trung tâm.', 'walking'),
        makeDalatActivityNote('noon', 'Mua đặc sản Đà Lạt & Trả phòng', 'Chợ Đà Lạt', 'Mua dâu tươi, mứt, trà atiso và cà phê từ các quầy có nguồn gốc rõ ràng trước khi trả phòng.', { lat: 11.9404, lng: 108.4376 }, 'Chợ Đà Lạt, Phường 1, TP. Đà Lạt', 'Đi bộ khoảng 5 phút từ khu Hòa Bình đến chợ.', 'walking'),
        makeDalatActivityNote('afternoon', 'Khởi hành từ Đà Lạt về lại TP. Hồ Chí Minh', 'Sân bay Liên Khương / Tuyến xe về TP.HCM', 'Xe tiễn ra sân bay Liên Khương hoặc xe limousine xuôi đèo Prenn - QL20 về lại TP. Hồ Chí Minh, kết thúc chuyến đi 7 ngày trọn vẹn.', { lat: 11.7501, lng: 108.3660 }, 'Sân bay Liên Khương, Huyện Đức Trọng, Lâm Đồng', 'Lái xe khoảng 35 - 45 phút từ trung tâm theo cao tốc Liên Khương.', 'driving'),
      ],
    },
  ];

  const days = dayDefinitions.slice(0, daysCount).map((definition, index) => {
    definition.slots.forEach(slot => {
      slot.transitMode ??= detectTransitMode({
        title: slot.activityTitle || slot.product?.name,
        transitInfo: slot.transitInfo,
        transitMode: slot.transitMode,
      });
      if (slot.product) {
        totalEstimatedPrice += slot.product.unitPrice * 2;
        bookableProductsCount++;
      }
    });
    return { day: index + 1, title: definition.title, slots: definition.slots };
  });

  return {
    intent,
    title: isMultiHotel
      ? `Lịch trình ${daysCount} ngày ở Đà Lạt (Trải nghiệm 2 khách sạn)`
      : `Lịch trình ${daysCount} ngày ở Đà Lạt`,
    stay,
    stays,
    days,
    totalEstimatedPrice,
    bookableProductsCount,
    fallback: false,
  };
}

export function buildGroundedItinerary(
  intent: TravelIntent,
  user: UserPersona | null,
  userEvents: UserEvent[] = []
): GroundedPlan {
  const dest = intent.destination;
  if (dest === 'Đà Lạt') {
    return buildDalatItinerary(intent, user, userEvents);
  }

  const destProducts = CATALOG.filter(p => p.destination === dest && p.available);
  const hotels = destProducts.filter(p => p.taxonomy === 'hotel');
  const attractions = destProducts.filter(p => p.taxonomy === 'attraction');
  const combos = destProducts.filter(p => p.taxonomy === 'combo');
  const recs = calculateRecommendations(user, userEvents);

  const daysCount = intent.days || 3;
  const isMultiHotel = Boolean(intent.multiHotel && hotels.length >= 2);

  let stay: GroundedPlan['stay'] = undefined;
  let stays: GroundedPlan['stays'] = undefined;
  let totalEstimatedPrice = 0;
  let bookableProductsCount = 0;

  const preferVillaOrPool = intent.interests?.some(i => i === 'villa' || i === 'pool');
  const matchedHotel = preferVillaOrPool 
    ? hotels.find(h => h.name.toLowerCase().includes('biệt thự') || h.attributes?.pool) 
    : undefined;
  const primaryStayProduct = matchedHotel || hotels[0] || CATALOG.find(p => p.taxonomy === 'hotel')!;

  if (isMultiHotel) {
    const totalNights = Math.max(2, daysCount - 1);
    const nights1 = Math.ceil(totalNights / 2);
    const nights2 = totalNights - nights1;

    const hotel1 = hotels[0];
    const hotel2 = hotels[1];

    let source1: 'recommendation' | 'search' = 'search';
    let source2: 'recommendation' | 'search' = 'search';
    let because1 = undefined;
    let because2 = undefined;

    if (user && recs.recommendations.some(r => r.product.id === hotel1.id)) {
      source1 = 'recommendation';
      because1 = recs.recommendations.find(r => r.product.id === hotel1.id)?.because;
    }
    if (user && recs.recommendations.some(r => r.product.id === hotel2.id)) {
      source2 = 'recommendation';
      because2 = recs.recommendations.find(r => r.product.id === hotel2.id)?.because;
    }

    stays = [
      {
        productId: hotel1.id,
        product: hotel1,
        nights: nights1,
        dayRange: `Chặng 1: Đêm 1${nights1 > 1 ? ` - ${nights1}` : ''} (Ngày 1 - ${nights1 + 1})`,
        note: `Nghỉ dưỡng ${nights1} đêm đầu tại ${hotel1.name} với vị trí đắc địa và dịch vụ tiện nghi.`,
        source: source1,
        because: because1
      },
      {
        productId: hotel2.id,
        product: hotel2,
        nights: nights2,
        dayRange: `Chặng 2: Đêm ${nights1 + 1}${nights2 > 1 ? ` - ${totalNights}` : ''} (Ngày ${nights1 + 1} - ${daysCount})`,
        note: `Trải nghiệm ${nights2} đêm tiếp theo tại ${hotel2.name} để đổi mới không gian và tận hưởng kỳ nghỉ phong phú.`,
        source: source2,
        because: because2
      }
    ];

    totalEstimatedPrice += hotel1.unitPrice * nights1 + hotel2.unitPrice * nights2;
    bookableProductsCount += 2;
  } else {
    let stayProduct = primaryStayProduct;
    let staySource: 'recommendation' | 'search' = 'search';
    let stayBecause = undefined;

    if (user && recs.recommendations.some(r => r.product.id === stayProduct.id)) {
      staySource = 'recommendation';
      stayBecause = recs.recommendations.find(r => r.product.id === stayProduct.id)?.because;
    }

    stay = {
      productId: stayProduct.id,
      product: stayProduct,
      note: 'Chỗ nghỉ trung tâm cao cấp cho cả hành trình với bãi biển riêng, hồ bơi lớn và dịch vụ trọn gói.',
      source: staySource,
      because: stayBecause
    };
    totalEstimatedPrice += stayProduct.unitPrice * Math.max(1, daysCount - 1);
    bookableProductsCount += 1;
  }

  const days: GroundedPlan['days'] = [];

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
          timeRange: '08:30 - 11:30',
          activityTitle: `Khám phá & Vui chơi tại ${attr.name}`,
          locationName: attr.name,
          productId: attr.id,
          product: attr,
          note: intent.party === 'family_with_kids' 
            ? 'Khởi hành sớm để các bé tránh nắng gắt, thỏa sức vui chơi công viên nước và thủy cung.' 
            : 'Check-in buổi sáng với các trò chơi cảm giác mạnh và ngắm trọn cảnh vịnh.',
          source: 'search',
          coordinates: attr.coordinates,
          address: attr.address,
          transitMode: dest === 'Nha Trang' ? 'cable' : 'driving',
          transitInfo: dest === 'Nha Trang'
            ? 'Di chuyển ~15 phút bằng cáp treo vượt biển / cano sang đất liền ăn trưa'
            : 'Di chuyển ~15 phút sang khu vực ẩm thực ăn trưa'
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
        timeRange: '11:45 - 13:30',
        isActivityNote: true,
        activityTitle: 'Nghỉ ngơi & Ăn trưa ẩm thực địa phương',
        locationName: noonAddress.split(',')[0],
        note: 'Thưởng thức bữa trưa đặc sản địa phương tươi sống tại khu ẩm thực, nghỉ ngơi lấy lại năng lượng.',
        coordinates: noonCoord,
        address: noonAddress,
        transitMode: dest === 'Nha Trang' ? 'ferry' : 'driving',
        transitInfo: dest === 'Nha Trang'
          ? 'Di chuyển ~20 phút bằng cano / tàu cao tốc trở lại đảo Hòn Tre dự show tối'
          : 'Di chuyển ~20 phút về khu nghỉ dưỡng chuẩn bị cho show tối'
      });

      // Evening combo
      const combo = combos[0] || destProducts.find(p => p.taxonomy === 'combo');
      if (combo) {
        slots.push({
          time: 'evening',
          timeRange: '18:00 - 21:00',
          activityTitle: `Thưởng thức ${combo.name}`,
          locationName: combo.name,
          productId: combo.id,
          product: combo,
          note: 'Thưởng thức show diễn công nghệ ánh sáng đỉnh cao kết hợp tiệc tối hải sản sang trọng.',
          source: 'recommendation',
          coordinates: combo.coordinates,
          address: combo.address,
          transitInfo: 'Trở về khách sạn nghỉ ngơi, tự do dạo biển đêm',
          because: [
            {
              productName: primaryStayProduct.name,
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
          timeRange: '08:00 - 11:30',
          activityTitle: `Tham quan & Trải nghiệm tại ${attr2.name}`,
          locationName: attr2.name,
          productId: attr2.id,
          product: attr2,
          note: 'Trải nghiệm thiên nhiên bán hoang dã và tương tác trực tiếp với các loài động vật quý.',
          source: 'search',
          coordinates: attr2.coordinates,
          address: attr2.address,
          transitInfo: 'Di chuyển ~10 phút đến điểm cà phê ven biển'
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
          timeRange: '08:00 - 11:00',
          isActivityNote: true,
          activityTitle: 'Tắm biển & Dạo ngắm bình minh trên bãi cát',
          locationName: `Bãi biển riêng tại ${dest}`,
          note: 'Thức dậy ngắm bình minh tuyệt đẹp, tắm biển tại bãi tắm riêng của khu nghỉ dưỡng và dùng buffet sáng.',
          coordinates: morningBeachCoord,
          address: `Bãi biển tuyệt đẹp tại ${dest}`,
          transitMode: 'walking',
          transitInfo: 'Tản bộ dạo ngắm bình minh trên bãi cát và dùng buffet sáng'
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
        timeRange: '11:45 - 13:30',
        isActivityNote: true,
        activityTitle: 'Thưởng thức cà phê & ẩm thực ven biển',
        locationName: `Quán Cà Phê & Ẩm Thực Biển ${dest}`,
        note: 'Ghé quán cà phê view biển ngắm sóng, thưởng thức dừa xiêm và đặc sản tươi ngon trứ danh.',
        coordinates: cafeCoord,
        address: `Quán cà phê & ẩm thực ven biển trung tâm ${dest}`,
        transitInfo: 'Di chuyển ~15 phút sang Akoya Spa & bãi tắm riêng'
      });

      // Afternoon / Evening
      const spaCoord = dest === 'Nha Trang'
        ? { lat: 12.2132, lng: 109.2482 }
        : dest === 'Phú Quốc'
          ? { lat: 10.3340, lng: 103.8562 }
          : dest === 'Đà Nẵng'
            ? { lat: 16.0020, lng: 108.2610 }
            : (primaryStayProduct?.coordinates || { lat: 12.2132, lng: 109.2482 });
      slots.push({
        time: 'afternoon',
        timeRange: '14:30 - 17:30',
        isActivityNote: true,
        activityTitle: 'Trải nghiệm spa thư giãn hoặc chèo kayak',
        locationName: 'Akoya Spa & Khu nghỉ dưỡng',
        note: 'Thư giãn trị liệu bằng tinh dầu thảo mộc tại Akoya Spa hoặc chèo kayak trên mặt biển êm đềm.',
        coordinates: spaCoord,
        address: `Akoya Spa & khu vực bãi biển riêng tại ${dest}`,
        transitInfo: 'Tự do khám phá phố đêm và ẩm thực đường phố'
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
        timeRange: '08:30 - 11:00',
        isActivityNote: true,
        activityTitle: 'Thong thả ngắm cảnh & Mua sắm đặc sản làm quà',
        locationName: `Khu chợ đặc sản ${dest}`,
        note: 'Mua sắm yến sào, chả cá, khô mực hoặc ngọc trai uy tín tại trung tâm trước khi làm thủ tục trả phòng.',
        coordinates: marketCoord,
        address: `Khu chợ & trung tâm đặc sản truyền thống tại ${dest}`,
        transitInfo: 'Trở về khách sạn làm thủ tục trả phòng'
      });
      slots.push({
        time: 'noon',
        timeRange: '11:30 - 13:30',
        isActivityNote: true,
        activityTitle: 'Làm thủ tục trả phòng & Xe tiễn sân bay',
        locationName: `Sân bay kết nối ${dest}`,
        note: 'Thư thả ăn trưa nhẹ, trả phòng khách sạn và đón xe di chuyển ra sân bay kết thúc chuyến đi trọn vẹn.',
        coordinates: airportCoord,
        address: `Sân bay kết nối ${dest}`,
        transitMode: 'flight',
        transitInfo: 'Xe đón tiễn ra sân bay và làm thủ tục chuyến bay'
      });
    }

    slots.forEach((slot) => {
      slot.transitMode ??= detectTransitMode({
        title: slot.activityTitle || slot.product?.name,
        transitInfo: slot.transitInfo,
        transitMode: slot.transitMode,
      });
    });

    days.push({
      day: d,
      title: dayTitle,
      slots
    });
  }

  return {
    intent,
    title: isMultiHotel 
      ? `Lịch trình ${daysCount} ngày ở ${dest} (Trải nghiệm 2 khách sạn)` 
      : `Lịch trình ${daysCount} ngày ở ${dest}`,
    stay,
    stays,
    days,
    totalEstimatedPrice,
    bookableProductsCount,
    fallback: false
  };
}

const DESTINATION_DEFAULT_COORDS: Record<string, { lat: number; lng: number }> = {
  'Nha Trang': { lat: 12.2388, lng: 109.1967 },
  'Phú Quốc': { lat: 10.2899, lng: 103.9840 },
  'Đà Nẵng': { lat: 16.0544, lng: 108.2022 },
  'Đà Lạt': { lat: 11.9404, lng: 108.4583 },
  'Hội An': { lat: 15.8801, lng: 108.3380 },
  'Hạ Long': { lat: 20.9505, lng: 107.0734 },
  'Hà Nội': { lat: 21.0285, lng: 105.8542 },
};

export function convertItineraryResponseToGroundedPlan(
  response: components['schemas']['ItineraryResponse'] | null | undefined
): GroundedPlan | null {
  if (!response || response.status !== 'COMPLETED' || !response.itinerary) return null;
  const itinerary = response.itinerary;
  const intentDestination = (response.intent?.destination || 'Nha Trang') as Destination;
  const defaultCoord = DESTINATION_DEFAULT_COORDS[intentDestination] || { lat: 12.2388, lng: 109.1967 };

  const mapProductSummaryToProduct = (summary: components['schemas']['ProductSummary']): Product => {
    const catalogItem = CATALOG.find((p) => p.id === summary.productId);
    return {
      id: summary.productId,
      name: summary.name,
      destination: (summary.destination || intentDestination) as Destination,
      taxonomy: summary.taxonomy as Product['taxonomy'],
      unitPrice: summary.unitPrice ?? catalogItem?.unitPrice ?? 0,
      currency: 'VND',
      imageUrl: summary.imageUrl || catalogItem?.imageUrl || '/placeholders/hotel.webp',
      coordinates: catalogItem?.coordinates || defaultCoord,
      address: catalogItem?.address || summary.destination,
      description: summary.name,
      attributes: (summary.attributes || catalogItem?.attributes || {}) as Product['attributes'],
      available: summary.available ?? true,
    };
  };

  const stay = itinerary.stay?.product
    ? {
        productId: itinerary.stay.product.productId,
        product: mapProductSummaryToProduct(itinerary.stay.product),
        note: itinerary.stay.note || 'Khách sạn lưu trú',
        source: (itinerary.stay.source as 'recommendation' | 'search' | undefined) || 'search',
      }
    : undefined;

  const days: ItineraryDay[] = (itinerary.days || []).map((d) => {
    const slots: ItinerarySlot[] = (d.slots || []).map((slot) => {
      const product = slot.product ? mapProductSummaryToProduct(slot.product) : undefined;
      const catalogItem = slot.product ? CATALOG.find((p) => p.id === slot.product.productId) : undefined;
      const coord = catalogItem?.coordinates || defaultCoord;
      const slotTime: ItinerarySlot['time'] = ['morning', 'noon', 'afternoon', 'evening'].includes(slot.time)
        ? (slot.time as ItinerarySlot['time'])
        : 'morning';

      return {
        time: slotTime,
        timeRange: slot.startTime && slot.endTime ? `${slot.startTime} - ${slot.endTime}` : undefined,
        locationName: product?.name || slot.activityType || 'Điểm hoạt động',
        productId: product?.id,
        product,
        note: slot.note || '',
        activityTitle: product?.name || slot.activityType || slot.note || 'Hoạt động',
        coordinates: coord,
        address: catalogItem?.address || intentDestination,
        transitMode: detectTransitMode({
          title: product?.name || slot.activityType,
          transitInfo: slot.note ?? undefined,
        }),
      };
    });

    return {
      day: d.day,
      title: d.title || `Ngày ${d.day}`,
      slots,
    };
  });

  let party: TravelIntent['party'] = 'family_with_kids';
  const rawParty = response.intent?.party as { type?: string } | string | undefined;
  const partyType = typeof rawParty === 'object' && rawParty !== null ? rawParty.type : rawParty;
  if (partyType === 'SOLO' || partyType === 'solo') party = 'solo';
  else if (partyType === 'COUPLE' || partyType === 'couple') party = 'couple';
  else if (partyType === 'FRIENDS' || partyType === 'friends') party = 'friends';
  else if (partyType === 'FAMILY_WITH_KIDS' || partyType === 'family_with_kids') party = 'family_with_kids';

  return {
    intent: {
      destination: intentDestination,
      days: response.intent?.days || days.length || 3,
      party,
      interests: response.intent?.interests || ['theme_park', 'beach'],
    },
    title: itinerary.title || `Lịch trình khám phá ${intentDestination}`,
    stay,
    days,
    totalEstimatedPrice: itinerary.estimatedTotal ?? 0,
    bookableProductsCount: itinerary.bookableCount ?? 0,
    fallback: false,
  };
}

