// ui/src/features/simulation/components/MembraneSelect.tsx
import React, { useEffect, useState, useMemo } from 'react';
import { UnitKind } from '../model/types';
import { MEMBRANE_CATALOG, MembraneSpec } from '../data/membrane_catalog';

const LABEL_CLS =
  'block text-[10px] font-bold text-slate-500 mb-1 uppercase tracking-wider';
const INPUT_BASE =
  'w-full border rounded px-2 py-1.5 text-xs focus:outline-none focus:border-blue-500 transition-colors font-mono placeholder:text-slate-600';
const INPUT_ENABLED = `${INPUT_BASE} bg-slate-950 border-slate-700 text-slate-200`;
const INPUT_DISABLED = `${INPUT_BASE} bg-slate-900/40 border-slate-800 text-slate-500 cursor-not-allowed`;
const SELECT_CLS =
  'w-full bg-slate-950 border border-slate-700 rounded px-2 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-blue-500';
const GROUP_CLS =
  'p-3 border border-slate-700/50 rounded-md bg-slate-900/30 mb-4';

const formatDisplayValue = (
  val: number | null | undefined,
  precision: number,
) => {
  if (val === null || val === undefined || isNaN(val)) return '';
  return parseFloat(val.toFixed(precision));
};

export const MembraneSelect: React.FC<{
  unitType: UnitKind;
  mode?: 'catalog' | 'custom' | 'db';
  model?: string;
  area?: number | null;
  A?: number | null;
  B?: number | null;
  rej?: number | null;
  onChange: (updates: any) => void;
}> = ({ unitType, mode = 'catalog', model, area, A, B, rej, onChange }) => {
  const [loading, setLoading] = useState(false);

  // 1. 유닛 타입(RO, HRRO, NF 등)에 맞게 멤브레인 필터링
  const list = useMemo(() => {
    if (unitType === 'HRRO')
      return MEMBRANE_CATALOG.filter(
        (m) => m.type === 'HRRO' || m.type === 'RO',
      );
    if (unitType === 'RO' || unitType === 'NF')
      return MEMBRANE_CATALOG.filter((m) => m.type === 'RO' || m.type === 'NF');
    return MEMBRANE_CATALOG.filter((m) => m.type === unitType);
  }, [unitType]);

  // 2. 제조사(Vendor)별로 그룹핑
  const groupedByVendor = useMemo(() => {
    const groups: Record<string, MembraneSpec[]> = {};
    list.forEach((m) => {
      const vendor = m.vendor || 'Other';
      if (!groups[vendor]) groups[vendor] = [];
      groups[vendor].push(m);
    });
    return groups;
  }, [list]);

  useEffect(() => {
    setLoading(true);
    const timer = setTimeout(() => setLoading(false), 50);
    return () => clearTimeout(timer);
  }, [unitType]);

  const handleModelChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newModelId = e.target.value;
    const spec = list.find((m) => m.id === newModelId);

    if (spec) {
      onChange({
        model: newModelId,
        area: spec.area_m2,
        A: spec.A_lmh_bar,
        B: spec.B_lmh ?? 0,
        rej: spec.salt_rejection_pct ?? 0,
      });
    } else {
      onChange({ model: '' });
    }
  };

  const isCustom = mode === 'custom';
  const isDiffusiveType = ['RO', 'NF', 'HRRO'].includes(unitType);

  // 🌟 [핵심 로직 추가] 카탈로그 모드인데 모델 선택이 안 되어 있으면 숫자를 숨겨버립니다.
  const getDisplayValue = (
    val: number | null | undefined,
    precision: number,
  ) => {
    if (!isCustom && !model) return ''; // 모델을 선택하지 않았으면 무조건 빈 문자열 반환
    return formatDisplayValue(val, precision);
  };

  // 모델 미선택 시 보여줄 플레이스홀더 텍스트
  const placeholderText = !isCustom && !model ? '모델 선택 대기 중' : '';

  return (
    <div className={GROUP_CLS}>
      <div className="flex items-center justify-between mb-3 border-b border-slate-800/50 pb-2">
        <h4 className="text-xs font-bold text-slate-300 flex items-center gap-2">
          🔹 멤브레인 규격 (ELEMENT)
          {loading && (
            <span className="text-[9px] text-blue-500 animate-pulse">●</span>
          )}
        </h4>
        <div className="flex bg-slate-950 rounded p-0.5 border border-slate-800">
          <button
            className={`px-2 py-0.5 text-[10px] rounded transition-colors ${!isCustom ? 'bg-slate-800 text-blue-400 font-bold' : 'text-slate-500 hover:text-slate-300'}`}
            onClick={() => onChange({ mode: 'catalog' })}
          >
            카탈로그
          </button>
          <div className="w-[1px] bg-slate-800 mx-0.5 my-1"></div>
          <button
            className={`px-2 py-0.5 text-[10px] rounded transition-colors ${isCustom ? 'bg-slate-800 text-emerald-400 font-bold' : 'text-slate-500 hover:text-slate-300'}`}
            onClick={() => onChange({ mode: 'custom' })}
          >
            직접 입력
          </button>
        </div>
      </div>

      {!isCustom ? (
        <div className="mb-3">
          <select
            className={SELECT_CLS}
            value={model || ''}
            onChange={handleModelChange}
            disabled={loading}
          >
            <option value="" disabled>
              -- 제조사 및 모델 선택 --
            </option>
            {Object.entries(groupedByVendor).map(([vendor, models]) => (
              <optgroup key={vendor} label={`🏢 ${vendor}`}>
                {models.map((m) => (
                  <option key={m.id} value={m.id}>
                    [{m.category}] {m.name} ({m.area_m2}m²)
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </div>
      ) : (
        <div className="mb-3 p-2 bg-emerald-900/10 border border-emerald-500/20 rounded text-[10px] text-emerald-400 flex items-center gap-2">
          <span>✨</span>
          <span>사용자 정의 모드 활성화. 아래 스펙을 직접 수정하세요.</span>
        </div>
      )}

      <div className="grid grid-cols-2 gap-x-4 gap-y-3">
        <div>
          <label className={LABEL_CLS}>유효 면적 (Area, m²)</label>
          <input
            type={!isCustom && !model ? 'text' : 'number'}
            className={isCustom ? INPUT_ENABLED : INPUT_DISABLED}
            value={getDisplayValue(area, 2)}
            placeholder={placeholderText}
            disabled={!isCustom}
            onChange={(e) => onChange({ area: Number(e.target.value) })}
          />
        </div>
        <div>
          <label className={LABEL_CLS}>투과 계수 (A-Value, lmh/bar)</label>
          <input
            type={!isCustom && !model ? 'text' : 'number'}
            className={isCustom ? INPUT_ENABLED : INPUT_DISABLED}
            value={getDisplayValue(A, 3)}
            placeholder={placeholderText}
            disabled={!isCustom}
            onChange={(e) => onChange({ A: Number(e.target.value) })}
          />
        </div>

        {isDiffusiveType && (
          <>
            <div>
              <label className={LABEL_CLS}>염 투과 계수 (B-Value, lmh)</label>
              <input
                type={!isCustom && !model ? 'text' : 'number'}
                className={isCustom ? INPUT_ENABLED : INPUT_DISABLED}
                value={getDisplayValue(B, 6)}
                placeholder={placeholderText}
                disabled={!isCustom}
                onChange={(e) => onChange({ B: Number(e.target.value) })}
              />
            </div>
            <div>
              <label className={LABEL_CLS}>염 제거율 (Rejection, %)</label>
              <input
                type={!isCustom && !model ? 'text' : 'number'}
                className={isCustom ? INPUT_ENABLED : INPUT_DISABLED}
                value={getDisplayValue(rej, 2)}
                placeholder={placeholderText}
                disabled={!isCustom}
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
