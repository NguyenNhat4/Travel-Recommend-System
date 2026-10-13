import React, { useState } from 'react';
import { useAssistant } from '../../../context/AssistantProvider';
export function AssistantProgressDiagnostics() {
  const {state}=useAssistant();
  const [copied,setCopied]=useState(false);
  let elapsed=0;
  return <section className="space-y-2 break-words" aria-label="Trợ lý — lượt gần nhất">
    <h3 className="font-semibold text-amber-300">Trợ lý — lượt gần nhất</h3>
    <p>Request: {state.run?.requestId ?? 'Chưa có lượt'}</p><p>Run: {state.run?.runId ?? '—'}</p><p>Loại: {state.progressModel.turnKind ?? '—'}</p>
    {state.run && <button type="button" className="min-h-11 text-amber-300 underline" onClick={() => {
      void navigator.clipboard.writeText(state.run!.requestId).then(() => setCopied(true)).catch(() => setCopied(false));
    }}>{copied ? 'Đã sao chép' : 'Sao chép requestId'}</button>}
    <table className="w-full text-left"><thead><tr><th>Bước</th><th>ms</th><th>Cộng dồn</th></tr></thead>
      <tbody>{state.progress.map((p,index) => {elapsed+=p.durationMs ?? 0;return <tr key={index}><td>{p.nodeId}<p>{p.outcome}</p></td><td>{p.durationMs}</td><td>{elapsed}</td></tr>;})}</tbody>
    </table>
    {state.activities.map((a,index) => <p key={index}>{a.nodeId} · {a.code} · vòng {a.round ?? '—'} · +{state.run ? a.at-state.run.startedAt : 0} ms</p>)}
    {(state.progressModel.searches ?? []).map((g) => <div key={g.groupId}><p>{g.groupId} · {g.status}</p><pre className="whitespace-pre-wrap break-words">{JSON.stringify(g.counts,null,2)}</pre></div>)}
    {state.previewAt && <p>Preview: +{state.previewAt-(state.run?.startedAt ?? state.previewAt)} ms</p>}
    {state.completedAt && <p>Kết quả: +{state.completedAt-(state.run?.startedAt ?? state.completedAt)} ms</p>}
  </section>;
}
