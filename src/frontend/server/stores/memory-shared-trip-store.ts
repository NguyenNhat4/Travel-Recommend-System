import type { SharedTripRecord, SharedTripStore } from './shared-trip-store';

export class MemorySharedTripStore implements SharedTripStore {
  private readonly trips = new Map<string, SharedTripRecord>();

  async create(trip: SharedTripRecord): Promise<void> {
    this.trips.set(trip.id, trip);
  }

  async getAndIncrementViews(id: string): Promise<SharedTripRecord | null> {
    const trip = this.trips.get(id);
    if (!trip) return null;

    trip.views += 1;
    return trip;
  }
}
