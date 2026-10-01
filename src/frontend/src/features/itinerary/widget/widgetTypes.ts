import type { GroundedPlan } from '../../../types/travel';
import type { AssistantCartItem } from '../../../components/assistant/AssistantResultPanel';
import type { ClarificationForm } from '../../../components/assistant/TripDetailsForm';

export type WidgetPlan = GroundedPlan & { cartItems: AssistantCartItem[] };

export interface WidgetChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  plan?: WidgetPlan;
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
