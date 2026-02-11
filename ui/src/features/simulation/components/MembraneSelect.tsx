// ui/src/features/simulation/components/MembraneSelect.tsx

import React, { useEffect, useState, useMemo } from 'react';

// 1. 필요한 타입만 불러오기
import { UnitKind } from '../model/types';

// 2. 외부 데이터 파일 연결
import { MEMBRANE_CATALOG, MembraneSpec } from '../data/membrane_catalog';

// ==========================================
// 1. 스타일 상수 (Tailwind)
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

// ==========================================
// 2. Props 타입 정의
// ==========================================
type Props = {
  unitType: UnitKind;
  mode?: 'catalog' | 'custom';
  model?: string;
  // 부모 컴포넌트에서 내려주는 현재 값 (화면 표시용)
  area?: number | null;
  A?: number | null;
  B?: number | null;
  rej?: number | null;
  // 변경 사항을 부모에게 알리는 함수
  onChange: (updates: any) => void;
};

// ==========================================
// 3. 메인 컴포넌트
// ==========================================
export const MembraneSelect: React.FC<Props> = ({
  unitType,
  mode = 'catalog',
  model,
  area,
  A,
  B,
  rej,
  onChange,
}) => {
  const [loading, setLoading] = useState(false);

  // 1. 멤브레인 목록 필터링 (useMemo로 최적화)
  const list = useMemo(() => {
    // HRRO는 HRRO 전용(SOAR 등)과 일반 RO를 모두 보여줄 수 있음
    // 우선순위: HRRO > RO
    if (unitType === 'HRRO') {
      return MEMBRANE_CATALOG.filter(
        (m) => m.type === 'HRRO' || m.type === 'RO',
      );
    }
    // RO/NF는 서로 호환 가능성 열어둠
    if (unitType === 'RO' || unitType === 'NF') {
      return MEMBRANE_CATALOG.filter((m) => m.type === 'RO' || m.type === 'NF');
    }
    // 그 외(UF, MF)는 자기 타입만
    return MEMBRANE_CATALOG.filter((m) => m.type === unitType);
  }, [unitType]);

  // 목록 로딩 효과 (UX)
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
      // 데이터 정규화 (값이 없으면 0 처리)
      const val_A = spec.A_lmh_bar;
      // B값: m/s -> LMH 변환 (3.6e6) - 카탈로그에 B_mps가 있으면 변환, 없으면 0
      const val_B = spec.B_mps ? spec.B_mps * 3.6e6 : 0;
      const val_Rej = spec.salt_rejection_pct ?? 0;
      const val_Area = spec.area_m2;

      // 부모 컴포넌트(UnitForms)의 상태 일괄 업데이트
      onChange({
        membrane_model: newModelId,
        // (A) 시뮬레이션 로직용 값
        membrane_area_m2: val_Area,
        membrane_A_lmh_bar: val_A,
        membrane_B_lmh: val_B,
        membrane_salt_rejection_pct: val_Rej,
        // (B) UI 표시용 커스텀 값 (초기화 - 카탈로그 모드이므로)
        custom_area_m2: undefined,
        custom_A_lmh_bar: undefined,
        custom_B_lmh: undefined,
        custom_salt_rejection_pct: undefined,
      });
    } else {
      // 선택 취소
      onChange({ membrane_model: '' });
    }
  };

  const isCustom = mode === 'custom';
  // RO, NF, HRRO는 확산(Diffusion) 기반 모델이므로 B값과 Rejection 표시
  const isDiffusiveType = ['RO', 'NF', 'HRRO'].includes(unitType);

  return (
    <div className={GROUP_CLS}>
      {/* 헤더 & 모드 전환 버튼 */}
      <div className="flex items-center justify-between mb-3 border-b border-slate-800/50 pb-2">
        <h4 className="text-xs font-bold text-slate-300 flex items-center gap-2">
          🔹 ELEMENT TYPE
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
            onClick={() => onChange({ membrane_mode: 'catalog' })}
          >
            Catalog
          </button>
          <div className="w-[1px] bg-slate-800 mx-0.5 my-1"></div>
          <button
            className={`px-2 py-0.5 text-[10px] rounded transition-colors ${
              isCustom
                ? 'bg-slate-800 text-emerald-400 font-bold'
                : 'text-slate-500 hover:text-slate-300'
            }`}
            onClick={() => onChange({ membrane_mode: 'custom' })}
          >
            Custom
          </button>
        </div>
      </div>

      {/* Catalog 모드: 드롭다운 메뉴 */}
      {!isCustom ? (
        <div className="mb-3">
          <select
            className={SELECT_CLS}
            value={model || ''}
            onChange={handleModelChange}
            disabled={loading}
          >
            <option value="" disabled>
              -- Select Manufacturer Model --
            </option>
            {list.map((m) => (
              <option key={m.id} value={m.id}>
                {/* 벤더명과 모델명을 보기 좋게 포맷팅 */}
                {`[${m.vendor}] ${m.name} (${m.area_m2}m²)`}
              </option>
            ))}
          </select>
        </div>
      ) : (
        // Custom 모드: 안내 문구
        <div className="mb-3 p-2 bg-emerald-900/10 border border-emerald-500/20 rounded text-[10px] text-emerald-400 flex items-center gap-2">
          <span>✨</span>
          <span>Custom Mode enabled. Edit specs below directly.</span>
        </div>
      )}

      {/* 스펙 입력/표시 폼 (2열 그리드) */}
      <div className="grid grid-cols-2 gap-3">
        {/* 공통 필드: Area & A-Value */}
        <div>
          <label className={LABEL_CLS}>Area (m²)</label>
          <input
            type="number"
            className={isCustom ? INPUT_ENABLED : INPUT_DISABLED}
            value={area ?? ''}
            disabled={!isCustom}
            onChange={(e) =>
              onChange({ custom_area_m2: Number(e.target.value) })
            }
          />
        </div>
        <div>
          <label className={LABEL_CLS}>
            A-Value{' '}
            <span className="text-[9px] lowercase text-slate-500 ml-1">
              (lmh/bar)
            </span>
          </label>
          <input
            type="number"
            className={isCustom ? INPUT_ENABLED : INPUT_DISABLED}
            value={A ?? ''}
            disabled={!isCustom}
            onChange={(e) =>
              onChange({ custom_A_lmh_bar: Number(e.target.value) })
            }
          />
        </div>

        {/* 확산형(RO/NF/HRRO) 전용 필드: B-Value & Rejection */}
        {isDiffusiveType && (
          <>
            <div>
              <label className={LABEL_CLS}>
                B-Value{' '}
                <span className="text-[9px] lowercase text-slate-500 ml-1">
                  (lmh)
                </span>
              </label>
              <input
                type="number"
                className={isCustom ? INPUT_ENABLED : INPUT_DISABLED}
                value={B ?? ''}
                disabled={!isCustom}
                onChange={(e) =>
                  onChange({ custom_B_lmh: Number(e.target.value) })
                }
              />
            </div>
            <div>
              <label className={LABEL_CLS}>
                Rejection{' '}
                <span className="text-[9px] lowercase text-slate-500 ml-1">
                  (%)
                </span>
              </label>
              <input
                type="number"
                className={isCustom ? INPUT_ENABLED : INPUT_DISABLED}
                value={rej ?? ''}
                disabled={!isCustom}
                onChange={(e) =>
                  onChange({
                    custom_salt_rejection_pct: Number(e.target.value),
                  })
                }
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default MembraneSelect;
