import type { components } from '../../../types/api.gen';
export type ProgressUpdate = components['schemas']['AssistantProgressUpdate'];
export type ProgressActivity = components['schemas']['AssistantNodeActivity'];
export type ProgressModel = ProgressUpdate & { completed: string[] };
export const emptyProgress = (): ProgressModel => ({ completed: [] });

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
