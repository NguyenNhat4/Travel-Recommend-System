/**
 * V-OTA Travel Recommendation Demo - Domain Types
 * Based on spec: spec/recsys-internship-handbook-v3-vi.md & spec/ux-research-brief.md
 */

export type Taxonomy = 'hotel' | 'flight' | 'attraction' | 'combo' | 'golf';

export type Destination = 'Nha Trang' | 'Phú Quốc' | 'Đà Nẵng' | 'Hà Nội' | 'Hội An' | 'Hạ Long' | 'Đà Lạt';

export interface ProductAttributes {
  starRating?: number;
  oceanView?: boolean;
  familyFriendly?: boolean;
  pool?: boolean;
  spa?: boolean;
  privateBeach?: boolean;
  freeBreakfast?: boolean;
  cableCar?: boolean;
  themePark?: boolean;
  safari?: boolean;
  waterPark?: boolean;
  airline?: string;
  roundTrip?: boolean;
  durationHours?: number;
  holes?: number;
  [key: string]: any;
}

export interface Coordinates {
  lat: number;
  lng: number;
}

export type TransitMode = 'driving' | 'walking' | 'bicycle' | 'ferry' | 'cable' | 'flight';

export interface Product {
  id: string;
  name: string;
  taxonomy: Taxonomy;
  destination: Destination;
  /** null = chưa có giá (khách sạn/tuyến bay cấp cha, điểm công cộng); không phải miễn phí. */
  unitPrice: number | null;
  currency: 'VND';
  priceString?: string;
  imageUrl: string;
  description: string;
  attributes: ProductAttributes;
  available: boolean;
  availableFrom?: string;
  availableTo?: string;
  aggregateRating?: {
    score: number;
    count: number;
  };
  highlights?: string[];
  included?: string[];
  coordinates?: Coordinates;
  address?: string;
  /** attributes.level: property/route chỉ để xem, đặt qua tầng con room/flight. */
  level?: string;
  parentProductId?: string;
}

export type EventType = 'purchase' | 'add_to_cart' | 'product_view' | 'search';

export interface BecauseItem {
  productId?: string;
  productName: string;
  event: EventType;
  daysAgo: number;
  contribution: number; // 0.0 to 1.0 (qualitative dots: >=0.5: 3 dots, 0.2-0.5: 2 dots, <0.2: 1 dot)
  imageUrl?: string;
}

export type Strategy = 'cross_vertical' | 'popular' | 'dormant' | 'recent_views' | string;

export interface RecommendationDiagnostic {
  eventsUsed: number;
  coldStart: boolean;
  excludedVerticals: Taxonomy[];
  modelVersion: string;
  latencyMs?: number;
}

export interface RecommendationResponse {
  strategy: Strategy;
  nextVertical?: Taxonomy;
  destination?: Destination;
  recommendations: Array<{
    product: Product;
    score: number;
    rank: number;
    because: BecauseItem[];
  }>;
  diagnostics: RecommendationDiagnostic;
  generatedAt: string;
}

export interface UserPersona {
  id: string; // 'P1' | 'P2' | 'P3' | 'P4'
  code: string;
  name: string;
  email: string;
  avatarText: string;
  tagline: string;
  description: string;
  historySummary: string;
  coldStart: boolean;
  isDormant?: boolean;
  seedEvents: UserEvent[];
  activeDestination?: Destination;
  bookedVerticals?: Taxonomy[];
}

export interface UserEvent {
  id: string;
  userId: string;
  productId: string;
  productName?: string;
  eventType: EventType;
  taxonomy: Taxonomy;
  destination: Destination;
  timestamp: string;
  eventGroupId?: string;
}

// Giỏ hàng và đơn đặt chỗ dùng kiểu sinh từ OpenAPI: services/booking.ts (CartResponse, BookingResponse).

// Assistant & Itinerary Types
export interface TravelIntent {
  destination: Destination;
  days: number;
  party: 'solo' | 'couple' | 'family_with_kids' | 'friends';
  interests: string[];
  startDate?: string;
  multiHotel?: boolean;
}

export interface ItinerarySlot {
  time: 'morning' | 'noon' | 'afternoon' | 'evening';
  timeRange?: string; // e.g. "08:30 - 11:30"
  locationName?: string; // e.g. "VinWonders Nha Trang"
  transitInfo?: string; // e.g. "Di chuyển ~15 phút bằng xe điện sang điểm ăn trưa"
  transitMode?: TransitMode;
  productId?: string;
  product?: Product;
  note: string;
  source?: 'recommendation' | 'search' | 'curated';
  because?: BecauseItem[];
  isActivityNote?: boolean; // For free activity/dining advice not linked to product
  activityTitle?: string;
  /** `ActivityType` của API khi slot không có sản phẩm (MEAL, REST, FREE_TIME, TRANSFER, SIGHTSEEING). */
  activityType?: string;
  coordinates?: Coordinates;
  address?: string;
}

export interface ItineraryStayItem {
  productId: string;
  product: Product;
  nights: number;
  dayRange?: string; // e.g. "Đêm 1 - 2 (Ngày 1 - 2)"
  note?: string;
  source?: 'recommendation' | 'search';
  because?: BecauseItem[];
}

export interface ItineraryDay {
  day: number;
  title: string;
  slots: ItinerarySlot[];
}

export interface GroundedPlan {
  intent: TravelIntent;
  missing?: string[];
  title: string;
  stay?: {
    productId: string;
    product: Product;
    note: string;
    source: 'recommendation' | 'search';
    because?: BecauseItem[];
  };
  stays?: ItineraryStayItem[];
  days: ItineraryDay[];
  /** Tổng chi phí các sản phẩm trong lịch trình. `null` = backend chưa đủ căn cứ để tính, KHÔNG phải 0. */
  totalEstimatedPrice: number | null;
  bookableProductsCount: number;
  fallback?: boolean;
}

export interface SavedTrip {
  id: string;
  savedAt: string;
  plan: GroundedPlan;
  notes?: string;
}

export type AgentRole = 'general' | 'itinerary' | 'culinary' | 'budget';
export type GeminiModelChoice = 'gemini-3.5-flash' | 'gemini-3.1-flash-lite' | 'gemini-3.1-pro-preview' | 'auto';

export interface SharedTripRecord {
  id: string;
  plan: GroundedPlan;
  senderName?: string;
  note?: string;
  createdAt: string;
  views?: number;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant' | 'system';
  text: string;
  timestamp: string;
  role?: AgentRole;
  modelUsed?: string;
  plan?: GroundedPlan;
  clarification?: {
    prompt: string;
    missingFields: string[];
    suggestedDestinations: Destination[];
    suggestedDays: number[];
  };
  suggestedFollowUps?: string[];
}
