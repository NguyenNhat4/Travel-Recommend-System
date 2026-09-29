import type { components } from '../../types/api.gen';

type Schemas = components['schemas'];

// Backend chỉ trả key; nhãn hiển thị do Web sở hữu (docs/spec/hop-dong-tich-hop-frontend.md §6).

export const SLOT_TIME_LABEL: Record<Schemas['SlotTime'], string> = {
  MORNING: 'Sáng',
  NOON: 'Trưa',
  AFTERNOON: 'Chiều',
  EVENING: 'Tối',
};

export const BUDGET_STATUS_LABEL: Record<Schemas['BudgetStatus'], string> = {
  WITHIN_BUDGET: 'Trong ngân sách',
  OVER_BUDGET: 'Vượt ngân sách',
  NO_BUDGET: 'Chưa đặt ngân sách',
  UNKNOWN: 'Chưa đủ dữ liệu',
};

export const PARTY_TYPE_LABEL: Record<Schemas['PartyType'], string> = {
  SOLO: 'Một mình',
  COUPLE: 'Cặp đôi',
  FAMILY_WITH_KIDS: 'Gia đình có trẻ em',
  FRIENDS: 'Nhóm bạn',
};

export const ACTIVITY_TYPE_LABEL: Record<Schemas['ActivityType'], string> = {
  MEAL: 'Ăn uống',
  REST: 'Nghỉ ngơi',
  FREE_TIME: 'Tự do khám phá',
  TRANSFER: 'Di chuyển',
  SIGHTSEEING: 'Tham quan',
};

const TAXONOMY_LABEL: Record<string, string> = {
  hotel: 'Khách sạn',
  flight: 'Vé máy bay',
  attraction: 'Vé tham quan',
  combo: 'Combo',
  golf: 'Golf',
};

export function taxonomyLabel(taxonomy: string) {
  return TAXONOMY_LABEL[taxonomy] ?? 'Dịch vụ';
}

const PRICE_UNIT_SUFFIX: Record<Schemas['PriceUnit'], string> = {
  PER_NIGHT: '/ đêm',
  PER_PERSON: '/ khách',
  PER_PACKAGE: '/ gói',
  UNKNOWN: '',
};

export function priceUnitSuffix(priceUnit: Schemas['PriceUnit']) {
  return PRICE_UNIT_SUFFIX[priceUnit] ?? '';
}

// Node ID theo src/backend/app/agents/graph.py.
const NODE_LABEL: Record<string, string> = {
  intake: 'Nhận yêu cầu',
  classify: 'Phân loại yêu cầu',
  extract: 'Hiểu ý định',
  converse: 'Trò chuyện',
  clarify: 'Hỏi thêm thông tin',
  tool: 'Tìm sản phẩm',
  evaluate: 'Kiểm tra kết quả',
  compose: 'Xếp lịch trình',
  retry: 'Thử lại',
  dead_letter: 'Chuyển sang phương án dự phòng',
  finalize: 'Hoàn tất',
};

export function nodeLabel(nodeId: string | undefined) {
  return (nodeId && NODE_LABEL[nodeId]) || 'Đang xử lý';
}
