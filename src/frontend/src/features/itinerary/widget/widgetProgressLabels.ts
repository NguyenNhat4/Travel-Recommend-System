import type { components } from '../../../types/api.gen';
export const kindLabel: Record<string,string> = { hotel:'Khách sạn', attraction:'Điểm tham quan', golf:'Golf', combo:'Combo', flight:'Vé máy bay' };
export function shortDate(date?: string) { return date ? `${date.slice(8,10)}/${date.slice(5,7)}` : ''; }
export function scopeLabel(group: components['schemas']['AssistantSearchGroup']) {
  const s = group.scope ?? {};
  return [kindLabel[group.kind], s.origin && s.destination ? `${s.origin} → ${s.destination}` : s.destination,
    s.excludedDestinations?.length ? `ngoài ${s.excludedDestinations.join(', ')}` : null,
    s.date && shortDate(s.date), s.near && `gần ${s.near}`,
    s.intent === 'more' ? 'tìm thêm' : s.intent === 'cheaper' ? 'rẻ hơn' : s.intent === 'dearer' ? 'giá cao hơn' : null,
    s.sort === 'price_asc' ? 'giá thấp trước' : s.sort === 'price_desc' ? 'giá cao trước' : null].filter(Boolean).join(' · ');
}

export function jobExplanation(group: components['schemas']['AssistantSearchGroup']) {
  const scope = group.scope ?? {};
  const kind = kindLabel[group.kind]?.toLowerCase();
  if (!kind) return '';
  const location = scope.destination ? ` ở ${scope.destination}` : '';
  if (group.kind === 'flight') {
    const route = scope.origin && scope.destination ? ` ${scope.origin} → ${scope.destination}` : location;
    return `Mình tra vé máy bay${route}${scope.date ? ` ngày ${shortDate(scope.date)}` : ''} từ dữ liệu chuyến bay.`;
  }
  const opening = scope.intent === 'more'
    ? `Bạn muốn xem thêm ${kind}${location}. Mình tìm các lựa chọn mới và loại những nơi đã giới thiệu.`
    : scope.intent === 'about_shown'
      ? `Bạn hỏi về ${kind} đã xem. Mình tra lại đúng thẻ để xác nhận dữ liệu hiện tại.`
      : scope.intent === 'cheaper'
        ? `Bạn muốn ${kind}${location} rẻ hơn. Mình tra lại giá của lựa chọn đã xem để làm mốc so sánh.`
        : scope.intent === 'dearer'
          ? `Bạn muốn ${kind}${location} có giá cao hơn. Mình tra lại giá của lựa chọn đã xem để làm mốc so sánh.`
          : `Bạn đang tìm ${kind}${location}. Mình tra các lựa chọn trong phạm vi này.`;
  return [opening, scope.scopeMode === 'replace'
    ? scope.destination ? `Mình chuyển phạm vi tìm sang ${scope.destination} theo yêu cầu mới.`
      : 'Mình bỏ phạm vi thành phố cũ để tìm ở nhiều điểm đến.' : '',
    scope.excludedDestinations?.length ? `Lượt này không xét ${scope.excludedDestinations.join(', ')}.` : '',
    scope.requestedCount ? scope.requestedCount > 20
      ? `Bạn yêu cầu ${scope.requestedCount} lựa chọn; lượt này giới thiệu tối đa 20.`
      : `Mục tiêu là ${scope.requestedCount} lựa chọn; mình sẽ nói rõ nếu không tìm đủ.` : '',
    scope.near ? `Giữ phạm vi quanh ${scope.near}.` : '',
    scope.sort === 'price_asc' ? 'So sánh các kết quả tra được theo giá từ thấp đến cao.'
      : scope.sort === 'price_desc' ? 'So sánh các kết quả tra được theo giá từ cao đến thấp.' : ''].filter(Boolean).join(' ');
}
export function searchLabel(group: components['schemas']['AssistantSearchGroup']) {
  const label = scopeLabel(group), c = group.counts;
  if (group.status === 'failed' || group.status === 'unavailable') return `${label}: chưa tra được`;
  if (!c || c.inScope === undefined) return label;
  return `${label}: tìm thấy ${c.inScope}${c.sourceMore ? '+' : ''}${c.chosen !== undefined ? `, ${group.kind === 'flight' ? 'chọn' : 'giới thiệu'} ${c.chosen}` : ''}`;
}
const reasons: Record<string,string> = {
  PRODUCT_DROPPED_DATE:'chưa mở bán cho ngày đi', PRODUCT_DROPPED_UNAVAILABLE:'không còn chỗ',
  PRODUCT_DROPPED_PRICE:'không đáp ứng giới hạn giá', PRODUCT_DROPPED_PRICE_BASIS:'khác đơn vị giá yêu cầu',
  PRODUCT_DROPPED_ATTRIBUTES:'không đáp ứng tiện ích hoặc hạng sao bắt buộc', PRODUCT_DROPPED_NAMED_REQUIREMENT:'không khớp tên yêu cầu',
  SEEN:'bạn đã xem', DUPLICATE:'trùng nơi', PREFERENCE:'không hợp sở thích lưu trú',
};
export function noticeLabel(n: components['schemas']['AssistantProgressNotice']) {
  if (n.code === 'SEEN' && n.count) return `Bỏ ${n.count} ${kindLabel[n.kind ?? '']?.toLowerCase() ?? 'sản phẩm'} bạn đã xem để tránh lặp gợi ý giữa các lượt.`;
  if (n.code === 'DUPLICATE' && n.count) return `Bỏ ${n.count} ${kindLabel[n.kind ?? '']?.toLowerCase() ?? 'sản phẩm'} trùng nơi để các thẻ đại diện cho những lựa chọn khác nhau.`;
  if (reasons[n.code] && n.count) return `Bỏ ${n.count} ${kindLabel[n.kind ?? '']?.toLowerCase() ?? 'sản phẩm'} ${reasons[n.code]}`;
  return ({ RETRYING:'Tìm kiếm chưa phản hồi, đang thử lại', NO_FLIGHT:'Không có chuyến phù hợp với ngày đi',
    NOT_ON_SALE:`Ngày ${shortDate(n.date)} chưa mở bán, đây là lịch tham khảo`, OVER_BUDGET:'Tổng chi phí vượt ngân sách',
    NOTHING_NEW:'Đã hết kết quả mới trong phạm vi này', PLACE_NOT_FOUND:'Chưa có dữ liệu về nơi này',
    LOOKUP_FAILED:'Chưa tra được dữ liệu, kết quả tìm kiếm có thể chưa đầy đủ', PARTIAL_RESULTS:'Đã tra được một phần, còn kết quả chưa kiểm tra' } as Record<string,string>)[n.code] ?? '';
}
export function understoodLabels(u?: components['schemas']['AssistantUnderstood'], turnKind?: components['schemas']['AssistantProgressUpdate']['turnKind']) {
  if (!u) return [];
  // Also guard old stream payloads which still attach the saved trip to an exploration or fare job.
  const useTrip = turnKind ? turnKind === 'plan' || turnKind === 'clarify' : !u.jobs?.length;
  const i = useTrip ? u.intent ?? {} : {};
  const party = i.party;
  const lines = [[i.destination, shortDate(i.startDate ?? undefined), i.days && `${i.days} ngày`,
    party?.adults && `${party.adults} người lớn`, party?.children && `${party.children} trẻ em`, i.origin && `từ ${i.origin}`,
    typeof i.budget === 'number' && `ngân sách ${i.budget.toLocaleString('vi-VN')} ₫`,
    i.interests?.length && `thích ${i.interests.slice(0,3).join(', ')}${i.interests.length>3 ? ` +${i.interests.length-3}` : ''}`].filter(Boolean).join(' · ')];
  const missingLabels: Record<string,string> = { destination:'điểm đến', days:'số ngày', startDate:'ngày đi', party:'số người', origin:'nơi đi', budget:'ngân sách', interests:'sở thích' };
  if (useTrip && u.missing?.length) lines.push(`Còn thiếu: ${u.missing.map((f) => missingLabels[f]).filter(Boolean).join(', ')}`);
  const assumptions: Record<string,string> = {NO_BUDGET:'Ngân sách: chưa nêu → không giới hạn theo giá', NO_ORIGIN:'Nơi đi: chưa nêu → chưa tìm vé máy bay',DAY_TRIP:'Đi trong ngày → không kèm vé máy bay',FLIGHT_EXCLUDED:'Không cần vé máy bay → không tìm vé',SAME_CITY:'Nơi đi trùng điểm đến → không cần vé',KIDS_COUNT_UNKNOWN:'Gia đình có trẻ nhỏ: chưa rõ số trẻ'};
  for (const a of useTrip ? u.assumptions ?? [] : []) {
    const text = a.code==='NAME_MATCHED' ? `${a.from} → ${a.to}` : a.code==='ROOM_MIN_GUESTS' ? `Tìm phòng từ ${a.count} khách để đủ tối đa 9 phòng` : assumptions[a.code];
    if (text) lines.push(text);
  }
  if (!useTrip) for (const job of u.jobs ?? []) lines.push(jobExplanation({...job,status:'running'}));
  return lines.filter(Boolean);
}
