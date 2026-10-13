import type { AssistantProgress } from '../../../context/assistantState';
import { emptyProgress, mergeProgress, type ProgressModel, type ProgressActivity } from './progressModel';
import { searchLabel, noticeLabel, understoodLabels } from './widgetProgressLabels';
export type ProgressStepStatus = 'done' | 'active' | 'pending';
export interface ProgressStep { key: string; label: string; status: ProgressStepStatus; lines: string[]; notices: string[] }
export interface ProgressView { turnKind?: ProgressModel['turnKind']; steps: ProgressStep[]; current: string; summary: string }
const titles: Record<string,string> = {understand:'Hiểu yêu cầu',search:'Tìm sản phẩm phù hợp',arrange:'Sắp xếp lịch trình',write:'Viết lời tư vấn'};
const running: Record<string,string> = {understand:'Đang hiểu yêu cầu của bạn…',search:'Đang tìm sản phẩm phù hợp…',arrange:'Đang sắp xếp lịch trình theo ngày…',write:'Đang viết lời tư vấn…'};
const nodeStep: Record<string,string> = {intake:'understand',precheck:'understand',extract:'understand',clarify:'understand',tool:'search',evaluate:'search',retry:'search',run_jobs:'search',filter:'arrange',compose:'arrange',narrate:'write',gatekeep:'write',orchestrate:'understand'};
export function activityLabel(a?: ProgressActivity, kind?: ProgressModel['turnKind']) {
  if (!a) return '';
  const where = a.origin && a.destination ? `${a.origin} → ${a.destination}` : a.destination ?? '';
  const lookup: Record<string,string> = {PLANNING_SEARCH:'Đang chọn những thứ cần tìm cho chuyến đi…',SEARCHING:`Đang tìm sản phẩm${where ? ` ở ${where}` : ''}…`,SEARCHING_FLIGHTS:`Đang tra vé${where ? ` ${where}` : ''}…`,CHECKING_AVAILABILITY:'Đang kiểm tra giá và lịch trống…',READING_SHOWN:'Đang xem lại thẻ bạn hỏi…'};
  if (a.code !== 'STARTED') return lookup[a.code] ?? '';
  if (a.nodeId==='orchestrate' && (a.round ?? 1)>1) return 'Đang xem kết quả và soạn câu trả lời…';
  if (a.nodeId==='gatekeep') return 'Đang kiểm tra câu trả lời và các sản phẩm…';
  if (a.nodeId==='finalize') return 'Đang hoàn tất câu trả lời…';
  return running[nodeStep[a.nodeId]] ?? (kind==='fare' ? 'Đang tra vé…' : 'Đang xử lý yêu cầu…');
}
export function progressView(input: ProgressModel | AssistantProgress[], activity?: ProgressActivity, complete=false): ProgressView {
  let model: ProgressModel;
  if (Array.isArray(input)) {
    model = input.reduce((m,e) => mergeProgress(m,e.progress),emptyProgress());
  } else model=input;
  const known = new Set([...model.completed,...(model.steps ?? ['understand'])]);
  const keys = ['understand', 'search', 'arrange', 'write'].filter((key) => known.has(key));
  const activeKey = activity ? (activity.nodeId==='orchestrate' && (activity.round ?? 1)>1 ? 'write' : nodeStep[activity.nodeId]) : keys.find((k) => !model.completed.includes(k)) ?? keys[keys.length-1];
  const current = complete ? '' : activityLabel(activity,model.turnKind) || running[activeKey] || running.understand;
  const groups = (model.searches ?? []).filter((g) => g.status!=='superseded');
  const hidden = new Set((model.searches ?? []).filter((g) => g.status==='superseded').map((g) => g.groupId));
  const notices=(model.notices ?? []).filter((n) => !hidden.has(n.groupId ?? '')).map(noticeLabel).filter(Boolean);
  const arrange: Record<string,string> = {SHORTEST_DISTANCE:'tổng quãng đường ngắn nhất',MAX_TWO_ACTIVITIES_PER_DAY:'tối đa 2 hoạt động mỗi ngày',FLIGHT_TIMES:'khớp giờ bay',STAY_PREFERENCE:'ưu tiên sở thích lưu trú'};
  const steps = keys.map((key): ProgressStep => ({ key, label: !complete && key===activeKey ? current : key==='write' && model.turnKind==='explore' ? 'Giải thích và trả lời' : titles[key],
    status: model.turnKind==='blocked' ? 'pending' : !complete && key===activeKey ? 'active' : model.completed.includes(key) ? 'done' : 'pending',
    lines: key==='understand' ? understoodLabels(model.understood, model.turnKind) : key==='search' ? groups.map(searchLabel) : key==='arrange' && model.arranged ? [
      model.arranged.criteria?.length ? `Tối ưu theo: ${model.arranged.criteria.map((c) => arrange[c]).filter(Boolean).join(' · ')}` : '',
      model.arranged.stayOptions ? `${model.arranged.stayOptions} phương án khách sạn để so sánh` : '',
    ].filter(Boolean) : key==='write' ? ['Câu trả lời dùng dữ kiện vừa tra; các sản phẩm và số liệu được kiểm nguồn trước khi hiển thị.'] : [], notices: key==='search' ? notices : [], }));
  const summary = ['plan','explore','fare'].includes(model.turnKind ?? '') ? [
    model.turnKind==='plan' ? understoodLabels(model.understood, model.turnKind)[0] : '',
    ...groups.map(searchLabel), notices.length ? `${notices.length} lưu ý` : '',
  ].filter(Boolean).join(' · ') : '';
  return { turnKind:model.turnKind, steps,current,summary };
}
