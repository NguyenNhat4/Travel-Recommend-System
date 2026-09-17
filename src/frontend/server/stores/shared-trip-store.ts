export interface SharedTripRecord {
  id: string;
  plan: any;
  senderName?: string;
  note?: string;
  createdAt: string;
  views: number;
}

export interface SharedTripStore {
  create(trip: SharedTripRecord): Promise<void>;
  getAndIncrementViews(id: string): Promise<SharedTripRecord | null>;
}
