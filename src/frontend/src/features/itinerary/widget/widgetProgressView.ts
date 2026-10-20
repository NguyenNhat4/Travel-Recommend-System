import type { AssistantProgress } from '../../../context/assistantState';
import { emptyProgress, mergeProgress, type ProgressModel, type ProgressActivity } from './progressModel';
import { searchLabel, noticeLabel, understoodLabels, kindLabel } from './widgetProgressLabels';
export type ProgressStepStatus = 'done' | 'active' | 'pending';
export interface ProgressStep { key: string; label: string; status: ProgressStepStatus; lines: string[]; notices: string[]; tone?: 'think' | 'action' }
export interface ProgressView { turnKind?: ProgressModel['turnKind']; steps: ProgressStep[]; current: string; summary: string }
const titles: Record<string,string> = {understand:'Hiểu yêu cầu',search:'Tìm sản phẩm phù hợp',arrange:'Sắp xếp lịch trình',write:'Viết lời tư vấn'};
const running: Record<string,string> = {understand:'Đang hiểu yêu cầu của bạn…',search:'Đang tìm sản phẩm phù hợp…',arrange:'Đang sắp xếp lịch trình theo ngày…',write:'Đang viết lời tư vấn…'};
const nodeStep: Record<string,string> = {intake:'understand',precheck:'understand',extract:'understand',clarify:'understand',tool:'search',evaluate:'search',retry:'search',run_jobs:'search',filter:'arrange',compose:'arrange',narrate:'write',gatekeep:'write',orchestrate:'understand'};
type ActivityData = NonNullable<ProgressModel['timeline']>[number]['data'];
const capitalize = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);
/** "tìm khách sạn ở Vũng Tàu": động từ theo loại việc, đối tượng theo taxonomy, nơi theo destination. */
function workSentence(data: ActivityData) {
  const what = data.taxonomy ? kindLabel[data.taxonomy]?.toLowerCase() : '';
  const where = data.destination ? ` ở ${data.destination}` : '';
  const sentence: Record<string, string> = {
    search: `tìm ${what || 'lựa chọn'}${where}`, catalog: `tìm ${what || 'lựa chọn'}${where}`,
    recommend: `tìm gợi ý ${what || 'hợp với bạn'}${where}`, similar: `tìm ${what || 'lựa chọn'} tương tự${where}`,
    detail: `đọc chi tiết ${what || 'sản phẩm'}${where}`, destinations: `tìm điểm đến phù hợp${where}`,
    flights: `tra vé máy bay${where}`, itinerary: `xếp lịch và tính chi phí${where}`, answer: 'kiểm lại câu trả lời',
  };
  return sentence[data.kind] ?? '';
}
function resultLine({ kind, counts }: ActivityData) {
  if (kind === 'itinerary') return counts.eligible ? `Lịch gồm ${counts.eligible} sản phẩm.` : '';
  if (kind === 'answer' || kind === 'detail') return '';
  const found = counts.found > counts.eligible ? `${counts.eligible}/${counts.found} kết quả phù hợp` : `${counts.eligible} kết quả phù hợp`;
  return counts.displayed ? `${found}, chọn ${counts.displayed} để giới thiệu.` : `${found}.`;
}
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
  if (model.timeline) {
    // Think là một câu giải thích; Act và Observe của cùng groupId gộp thành một dòng việc viết thành câu liền mạch.
    const observed = new Map(model.timeline.filter((row) => row.phase === 'Observe').map((row) => [row.data.groupId, row.data]));
    let thinks = 0;
    // Cùng việc, cùng loại, cùng nơi lần thứ hai trở đi trong lượt là xem thêm (trang tiếp hoặc tìm lại), không phải việc mới.
    const seen = new Set<string>();
    const steps = model.timeline.filter((row) => row.phase !== 'Observe'
      || !model.timeline!.some((act) => act.phase === 'Act' && act.data.groupId === row.data.groupId))
      .map(({ key, phase, data: act }): ProgressStep => {
        // Think: tiêu đề ngắn theo vòng (vòng đầu đọc yêu cầu, các vòng sau xem kết quả), lời giải thích nằm dưới.
        // Think của quyết định trả lời có số do code đếm: ứng viên đã xem trong lượt và số orc chọn hiện.
        if (phase === 'Think' && act.counts.displayed) return { key, label: act.explanation ? 'Chọn gợi ý' : '',
          status: 'done', lines: [`Chọn ${act.counts.displayed} trong ${act.counts.found} ứng viên đã xem.`,
            act.explanation ?? ''], notices: [], tone: 'think' };
        if (phase === 'Think') return { key, label: act.explanation ? (thinks++ ? 'Đánh giá kết quả' : 'Phân tích yêu cầu') : '',
          status: 'done', lines: act.explanation ? [act.explanation] : [], notices: [], tone: 'think' };
        const data = observed.get(act.groupId) ?? act;
        const running = data.status === 'running';
        const scope = `${data.kind}|${data.taxonomy ?? ''}|${data.destination ?? ''}`;
        const again = ['search', 'catalog', 'recommend'].includes(data.kind) && seen.has(scope);
        seen.add(scope);
        const work = again ? workSentence(data).replace(/^tìm /, 'xem thêm ') : workSentence(data);
        const outcome = data.outcome === 'error' || data.status === 'failed' ? 'Chưa tra được dữ liệu.'
          : data.outcome === 'needs_input' ? 'Còn thiếu thông tin để tra cứu.'
          : data.outcome === 'empty' ? 'Chưa có kết quả phù hợp.'
          : running ? '' : resultLine(data);
        return { key, label: running ? `Đang ${work}…` : capitalize(work),
          status: running ? 'active' : data.status === 'failed' ? 'pending' : 'done', lines: [outcome].filter(Boolean),
          notices: data.status === 'partial' ? ['Kết quả chưa đầy đủ.'] : [], tone: 'action' };
      }).filter((step) => step.label);
    const active = [...steps].reverse().find((step) => step.status === 'active');
    const tasks = steps.filter((step) => step.tone === 'action');
    const summary = tasks.slice(0, 2).map((step) => step.label).join(' · ')
      + (tasks.length > 2 ? ` · +${tasks.length - 2} việc khác` : '');
    return { steps, current: complete ? '' : active?.label ?? (steps.length ? 'Đang cân nhắc bước tiếp theo…' : 'Đang phân tích yêu cầu…'),
      summary: complete ? summary : '' };
  }
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
