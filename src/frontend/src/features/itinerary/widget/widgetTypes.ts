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
}

export interface ConversationSession {
  id: string;
  title: string;
  timestamp: string;
  messages: WidgetChatMessage[];
  plan: WidgetPlan | null;
}
