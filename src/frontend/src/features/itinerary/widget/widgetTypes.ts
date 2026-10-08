import type { GroundedPlan, Product } from '../../../types/travel';
import type { AssistantCartItem } from '../../../components/assistant/AssistantResultPanel';
import type { ClarificationForm } from '../../../components/assistant/TripDetailsForm';

/** `partyLabel`: nhãn đoàn khách dựng từ `intent.party` của API; `null` khi chưa biết thì ẩn. */
export type WidgetPlan = GroundedPlan & { cartItems: AssistantCartItem[]; partyLabel: string | null };

export interface WidgetChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  plan?: WidgetPlan;
  /** Sản phẩm của response `COMPLETED` (`narrationProducts`) để dựng thẻ trong lời diễn giải. */
  products?: Record<string, Product>;
  clarificationForm?: ClarificationForm;
  suggestions?: string[];
  /** Hàng thẻ "Phương án khác" (contract 1.20.0 `stayOptions`, AC-AGT-04): thẻ đầu là lịch đang chọn. */
  stayOptions?: StayOptionCard[];
}

/**
 * Một thẻ khách sạn trong hàng "Phương án khác". `index` null là lịch đang chọn; còn lại là số để chọn
 * (`selectStayOption.index`). Chênh tiền/km do backend tính; `plan` là lịch đầy đủ để xem trước ở cột phải.
 */
export interface StayOptionCard {
  index: number | null;
  hotels: Product[];
  distanceKm: number;
  kmDelta: number;
  moneyDelta: number;
  overBudget: number | null;
  plan: WidgetPlan;
}

/** Một dòng trong panel lịch sử: dựng từ `AssistantConversationSummary` hoặc từ cuộc đang chat chưa kịp vào archive. */
export interface ConversationSession {
  id: string;
  title: string;
  timestamp: string;
}
