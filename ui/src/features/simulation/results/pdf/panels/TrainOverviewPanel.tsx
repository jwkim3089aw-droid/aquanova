// ui/src/features/simulation/results/pdf/panels/TrainOverviewPanel.tsx
import React from 'react';

export function TrainOverviewPanel({ stages }: { stages: any[] }) {
  if (!stages || stages.length === 0) return null;

  return (
    <div className="w-full print:break-inside-avoid border-2 border-slate-500 p-4 bg-slate-50/50">
      <div className="text-[11px] font-bold text-slate-800 uppercase tracking-widest mb-6">
        공정 트레인 맵 (Train Map, PFD-Lite)
      </div>

      {/* 💡 [PATCH] print:flex-wrap, print:gap-y-8 및 shrink-0 추가로 PDF 줄바꿈 완벽 대응 */}
      <div className="flex items-start justify-start gap-2 overflow-x-auto pb-4 print:overflow-visible print:flex-wrap print:gap-y-8">
        {/* 1. System Feed */}
        <div className="flex flex-col items-center mt-2 shrink-0">
          <div className="border-2 border-slate-800 bg-white px-3 py-1.5 text-[10px] font-black text-slate-800 text-center tracking-wide w-24">
            유입수 (FEED)
          </div>
        </div>

        {/* 2. Stages (UF -> HRRO 자동 연결) */}
        {stages.map((s, i) => {
          const type = (
            s.membrane_model ||
            s.type ||
            s.module_type ||
            'RO'
          ).toUpperCase();
          const stageName = s.stage ? `Stage ${s.stage}` : `Stage ${i + 1}`;

          return (
            <React.Fragment key={i}>
              <div className="flex flex-col items-center mt-4 shrink-0">
                <div className="text-slate-800 font-bold text-[14px]">
                  {'→'}
                </div>
              </div>

              <div className="flex flex-col items-center shrink-0">
                {/* Stage Box */}
                <div className="border-2 border-slate-800 bg-white px-4 py-2 text-center min-w-[100px] relative z-10">
                  <div className="text-[10px] font-bold text-slate-600">
                    스테이지 (Stage)
                  </div>
                  <div className="text-[12px] font-black text-blue-900 tracking-wider mt-0.5">
                    {stageName} {type}
                  </div>
                </div>

                {/* Brine Stream (아래로 빠지는 화살표) */}
                <div className="flex flex-col items-center">
                  <div className="w-0.5 h-6 bg-slate-800"></div>
                  <div className="text-[14px] font-bold text-slate-800 leading-none">
                    {'↓'}
                  </div>
                  <div className="text-[9px] font-bold text-slate-600 mt-1">
                    농축수 (Brine)
                  </div>
                </div>
              </div>
            </React.Fragment>
          );
        })}

        {/* 3. Final Product */}
        <div className="flex flex-col items-center mt-4 shrink-0">
          <div className="text-slate-800 font-bold text-[14px]">{'→'}</div>
        </div>
        <div className="flex flex-col items-center mt-2 shrink-0">
          <div className="border-2 border-emerald-700 bg-emerald-50 px-3 py-1.5 text-[10px] font-black text-emerald-900 text-center tracking-wide w-28">
            생산수 (PRODUCT)
          </div>
        </div>
      </div>

      {/* PDF 원본의 안내 문구 완벽 복원 */}
      <div className="mt-2 text-[9px] text-slate-500 font-medium">
        * 현재 계산 결과(stage_metrics)를 기반으로 공정 트레인 구조를 간단히
        시각화했습니다.
      </div>
    </div>
  );
}
