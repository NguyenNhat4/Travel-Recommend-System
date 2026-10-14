import type { components } from '../../../types/api.gen';
import type { components as V2 } from '../../../types/assistant-v2.gen';
export type ProgressUpdate = components['schemas']['AssistantProgressUpdate'];
export type ProgressActivity = components['schemas']['AssistantNodeActivity'];
export interface ProgressTimelineEntry {
  key: string;
  phase: 'Think' | 'Act' | 'Observe';
  data: V2['schemas']['ActivityData'];
}
export type ProgressModel = ProgressUpdate & { completed: string[]; timeline?: ProgressTimelineEntry[] };
export const emptyProgress = (): ProgressModel => ({ completed: [] });

export function mergeTimeline(model: ProgressModel, entry: ProgressTimelineEntry): ProgressModel {
  const rows = new Map((model.timeline ?? []).map((row) => [row.key, row]));
  if (entry.phase === 'Observe') {
    const key = `Act:${entry.data.groupId}`;
    const act = rows.get(key);
    if (act) rows.set(key, { ...act, data: { ...act.data, status: entry.data.status } });
  }
  rows.set(entry.key, entry);
  return { ...model, timeline: [...rows.values()] };
}

export function mergeProgress(model: ProgressModel, update?: ProgressUpdate): ProgressModel {
  if (!update) return model;
  const groups = new Map((model.searches ?? []).map((g) => [g.groupId, g]));
  for (const group of update.searches ?? []) groups.set(group.groupId, group);
  const key = (n: NonNullable<ProgressUpdate['notices']>[number]) => `${n.code}|${n.groupId ?? ''}|${n.date ?? ''}`;
  const notices = new Map((model.notices ?? []).map((n) => [key(n), n]));
  for (const notice of update.notices ?? []) notices.set(key(notice), notice);
  return { ...model, ...update, searches: [...groups.values()], notices: [...notices.values()],
    completed: [...new Set([...model.completed, ...(update.completedStep ? [update.completedStep] : [])])] };
}
