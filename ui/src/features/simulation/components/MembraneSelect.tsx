// ui/src/features/simulation/components/MembraneSelect.tsx

import React, { useEffect, useState, useMemo } from 'react';
import { UnitKind } from '../model/types';
import { MEMBRANE_CATALOG } from '../data/membrane_catalog';

// ==========================================
// 1. 스타일 및 헬퍼
// ==========================================
const LABEL_CLS =
  'block text-[10px] font-bold text-slate-500 mb-1 uppercase tracking-wider';
const INPUT_BASE =
  'w-full border rounded px-2 py-1.5 text-xs focus:outline-none focus:border-blue-500 transition-colors font-mono';
const INPUT_ENABLED = `${INPUT_BASE} bg-slate-950 border-slate-700 text-slate-200`;
const INPUT_DISABLED = `${INPUT_BASE} bg-slate-900/40 border-slate-800 text-slate-500 cursor-not-allowed`;
const SELECT_CLS =
  'w-full bg-slate-950 border border-slate-700 rounded px-2 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-blue-500';
const GROUP_CLS =
  'p-3 border border-slate-700/50 rounded-md bg-slate-900/30 mb-4';

// 표시용 숫자 포맷팅 (0.000000004 방지)
const formatDisplayValue = (
  val: number | null | undefined,
  precision: number,
) => {
  if (val === null || val === undefined || isNaN(val)) return '';
  return parseFloat(val.toFixed(precision));
};

// ==========================================
// 2. 메인 컴포넌트
// ==========================================
export const MembraneSelect: React.FC<{
  unitType: UnitKind;
  mode?: 'catalog' | 'custom' | 'db'; // 'db'와 'catalog'는 같은 의미로 처리
  model?: string;
  area?: number | null;
  A?: number | null;
  B?: number | null;
  rej?: number | null;
  onChange: (updates: any) => void;
}> = ({ unitType, mode = 'catalog', model, area, A, B, rej, onChange }) => {
  const [loading, setLoading] = useState(false);

  // 1. 멤브레인 목록 필터링
  const list = useMemo(() => {
    if (unitType === 'HRRO') {
      return MEMBRANE_CATALOG.filter(
        (m) => m.type === 'HRRO' || m.type === 'RO',
      );
    }
    if (unitType === 'RO' || unitType === 'NF') {
      return MEMBRANE_CATALOG.filter((m) => m.type === 'RO' || m.type === 'NF');
    }
    return MEMBRANE_CATALOG.filter((m) => m.type === unitType);
  }, [unitType]);

  useEffect(() => {
    setLoading(true);
    const timer = setTimeout(() => setLoading(false), 50);
    return () => clearTimeout(timer);
  }, [unitType]);

  // 2. 모델 선택 핸들러
  const handleModelChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newModelId = e.target.value;
    const spec = list.find((m) => m.id === newModelId);

    if (spec) {
      // ✅ [수정] 단순화된 키값 전송 (부모가 받아서 매핑함)
      onChange({
        model: newModelId,
        area: spec.area_m2,
        A: spec.A_lmh_bar,
        B: spec.B_mps ? spec.B_mps * 3.6e6 : 0,
        rej: spec.salt_rejection_pct ?? 0,
      });
    } else {
      onChange({ model: '' });
    }
  };

  // 'db' 혹은 'catalog'면 DB 모드로 인식
  const isCustom = mode === 'custom';
  const isDiffusiveType = ['RO', 'NF', 'HRRO'].includes(unitType);

  return (
    <div className={GROUP_CLS}>
      {/* 헤더 & 모드 전환 */}
      <div className="flex items-center justify-between mb-3 border-b border-slate-800/50 pb-2">
        <h4 className="text-xs font-bold text-slate-300 flex items-center gap-2">
          🔹 멤브레인 규격 (ELEMENT)
          {loading && (
            <span className="text-[9px] text-blue-500 animate-pulse">●</span>
          )}
        </h4>
        <div className="flex bg-slate-950 rounded p-0.5 border border-slate-800">
          <button
            className={`px-2 py-0.5 text-[10px] rounded transition-colors ${
              !isCustom
                ? 'bg-slate-800 text-blue-400 font-bold'
                : 'text-slate-500 hover:text-slate-300'
            }`}
            onClick={() => onChange({ mode: 'catalog' })} // ✅ 'membrane_mode' -> 'mode'
          >
            카탈로그
          </button>
          <div className="w-[1px] bg-slate-800 mx-0.5 my-1"></div>
          <button
            className={`px-2 py-0.5 text-[10px] rounded transition-colors ${
              isCustom
                ? 'bg-slate-800 text-emerald-400 font-bold'
                : 'text-slate-500 hover:text-slate-300'
            }`}
            onClick={() => onChange({ mode: 'custom' })} // ✅ 'membrane_mode' -> 'mode'
          >
            직접 입력
          </button>
        </div>
      </div>

      {/* 모델 선택 영역 */}
      {!isCustom ? (
        <div className="mb-3">
          <select
            className={SELECT_CLS}
            value={model || ''}
            onChange={handleModelChange}
            disabled={loading}
          >
            <option value="" disabled>
              -- 제조사 모델 선택 --
            </option>
            {list.map((m) => (
              <option key={m.id} value={m.id}>
                {`[${m.vendor}] ${m.name} (${m.area_m2}m²)`}
              </option>
            ))}
          </select>
        </div>
      ) : (
        <div className="mb-3 p-2 bg-emerald-900/10 border border-emerald-500/20 rounded text-[10px] text-emerald-400 flex items-center gap-2">
          <span>✨</span>
          <span>사용자 정의 모드 활성화. 아래 스펙을 직접 수정하세요.</span>
        </div>
      )}

      {/* 세부 스펙 (그리드) */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-3">
        <div>
          <label className={LABEL_CLS}>유효 면적 (Area, m²)</label>
          <input
            type="number"
            className={isCustom ? INPUT_ENABLED : INPUT_DISABLED}
            // ✅ formatDisplayValue는 보여줄 때만 사용
            value={formatDisplayValue(area, 2)}
            disabled={!isCustom}
            // ✅ [수정] custom_area_m2 -> area (부모가 매핑)
            onChange={(e) => onChange({ area: Number(e.target.value) })}
          />
        </div>
        <div>
          <label className={LABEL_CLS}>투과 계수 (A-Value, lmh/bar)</label>
          <input
            type="number"
            className={isCustom ? INPUT_ENABLED : INPUT_DISABLED}
            value={formatDisplayValue(A, 3)}
            disabled={!isCustom}
            // ✅ [수정] custom_A_lmh_bar -> A
            onChange={(e) => onChange({ A: Number(e.target.value) })}
          />
        </div>

        {isDiffusiveType && (
          <>
            <div>
              <label className={LABEL_CLS}>염 투과 계수 (B-Value, lmh)</label>
              <input
                type="number"
                className={isCustom ? INPUT_ENABLED : INPUT_DISABLED}
                value={formatDisplayValue(B, 6)}
                disabled={!isCustom}
                // ✅ [수정] custom_B_lmh -> B
                onChange={(e) => onChange({ B: Number(e.target.value) })}
              />
            </div>
            <div>
              <label className={LABEL_CLS}>염 제거율 (Rejection, %)</label>
              <input
                type="number"
                className={isCustom ? INPUT_ENABLED : INPUT_DISABLED}
                value={formatDisplayValue(rej, 2)}
                disabled={!isCustom}
                // ✅ [수정] custom_salt_rejection_pct -> rej
                onChange={(e) => onChange({ rej: Number(e.target.value) })}
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default MembraneSelect;
