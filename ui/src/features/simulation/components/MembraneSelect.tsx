// ui/src/features/simulation/components/MembraneSelect.tsx

import React, { useEffect, useState } from 'react';

// 1. 필요한 타입만 불러오기
import { UnitKind } from '../model/types';

// 2. 외부 데이터 파일 연결 (정석 구조)
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
// 3. 서브 컴포넌트: 입력 필드 레이아웃
// ==========================================

// [RO, NF, HRRO용 레이아웃] - B값, Rejection 포함
const RoLayout = ({ isCustom, area, A, B, rej, onChange }: any) => (
  <div className="grid grid-cols-2 gap-3 mt-3">
    <div>
      <label className={LABEL_CLS}>Area (m²)</label>
      <input
        type="number"
        className={isCustom ? INPUT_ENABLED : INPUT_DISABLED}
        value={area ?? ''}
        disabled={!isCustom}
        onChange={(e) => onChange({ custom_area_m2: Number(e.target.value) })}
      />
    </div>
    <div>
      <label className={LABEL_CLS}>
        A-Value{' '}
        <span className="text-[9px] lowercase text-slate-600">(lmh/bar)</span>
      </label>
      <input
        type="number"
        className={isCustom ? INPUT_ENABLED : INPUT_DISABLED}
        value={A ?? ''}
        disabled={!isCustom}
        onChange={(e) => onChange({ custom_A_lmh_bar: Number(e.target.value) })}
      />
    </div>
    <div>
      <label className={LABEL_CLS}>
        B-Value{' '}
        <span className="text-[9px] lowercase text-slate-600">(lmh)</span>
      </label>
      <input
        type="number"
        className={isCustom ? INPUT_ENABLED : INPUT_DISABLED}
        value={B ?? ''}
        disabled={!isCustom}
        onChange={(e) => onChange({ custom_B_lmh: Number(e.target.value) })}
      />
    </div>
    <div>
      <label className={LABEL_CLS}>
        Rejection{' '}
        <span className="text-[9px] lowercase text-slate-600">(%)</span>
      </label>
      <input
        type="number"
        className={isCustom ? INPUT_ENABLED : INPUT_DISABLED}
        value={rej ?? ''}
        disabled={!isCustom}
        onChange={(e) =>
          onChange({ custom_salt_rejection_pct: Number(e.target.value) })
        }
      />
    </div>
  </div>
);

// [UF, MF용 레이아웃] - Area, Permeability(A)만 사용
const UfLayout = ({ isCustom, area, A, onChange }: any) => (
  <div className="grid grid-cols-2 gap-3 mt-3">
    <div>
      <label className={LABEL_CLS}>Area (m²)</label>
      <input
        type="number"
        className={isCustom ? INPUT_ENABLED : INPUT_DISABLED}
        value={area ?? ''}
        disabled={!isCustom}
        onChange={(e) => onChange({ custom_area_m2: Number(e.target.value) })}
      />
    </div>
    <div>
      <label className={LABEL_CLS}>
        Permeability{' '}
        <span className="text-[9px] lowercase text-slate-600">(lmh/bar)</span>
      </label>
      <input
        type="number"
        className={isCustom ? INPUT_ENABLED : INPUT_DISABLED}
        value={A ?? ''}
        disabled={!isCustom}
        onChange={(e) => onChange({ custom_A_lmh_bar: Number(e.target.value) })}
      />
    </div>
  </div>
);

// ==========================================
// 4. 메인 컴포넌트
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
  const [list, setList] = useState<MembraneSpec[]>([]);
  const [loading, setLoading] = useState(false);

  // 1. 멤브레인 목록 불러오기 (데이터 파일 활용)
  useEffect(() => {
    setLoading(true);

    // HRRO는 기본적으로 RO 멤브레인을 사용함
    const queryType = unitType === 'HRRO' ? 'RO' : unitType;

    // 외부 데이터 파일(MEMBRANE_CATALOG)에서 필터링
    const filtered = MEMBRANE_CATALOG.filter((m) =>
      queryType === 'RO' || queryType === 'NF'
        ? m.type === 'RO' || m.type === 'NF' // RO와 NF는 서로 호환해서 보여줌
        : m.type === queryType,
    );

    // UX를 위해 아주 짧은 로딩 딜레이 (선택사항)
    const timer = setTimeout(() => {
      setList(filtered);
      setLoading(false);
    }, 50);

    return () => clearTimeout(timer);
  }, [unitType]);

  // 2. 모델 선택 시 자동 값 채우기 핸들러
  const handleModelChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newModelId = e.target.value;
    const spec = list.find((m) => m.id === newModelId);

    if (spec) {
      // 데이터 정규화 (값이 없으면 0 처리)
      const val_A = spec.A_lmh_bar;
      const val_B = spec.B_mps ? spec.B_mps * 3.6e6 : 0; // m/s 단위를 lmh로 변환 (필요시)
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
        // (B) UI 표시용 커스텀 값 (초기화)
        custom_area_m2: val_Area,
        custom_A_lmh_bar: val_A,
        custom_B_lmh: val_B,
        custom_salt_rejection_pct: val_Rej,
      });
    } else {
      // 선택 취소 시 모델명만 비움
      onChange({ membrane_model: '' });
    }
  };

  const isCustom = mode === 'custom';
  // RO, NF, HRRO는 확산(Diffusion) 기반 모델이므로 B값과 Rejection이 필요함
  const isDiffusiveType = ['RO', 'NF', 'HRRO'].includes(unitType);

  return (
    <div className={GROUP_CLS}>
      {/* 헤더 & 모드 전환 버튼 */}
      <div className="flex items-center justify-between mb-3 border-b border-slate-800/50 pb-2">
        <h4 className="text-xs font-bold text-slate-300 flex items-center gap-2">
          MEMBRANE SPEC
          {loading && (
            <span className="text-[9px] text-blue-500 animate-pulse">●</span>
          )}
        </h4>
        <div className="flex bg-slate-950 rounded p-0.5 border border-slate-800">
          <button
            className={`px-2 py-0.5 text-[10px] rounded transition-colors ${!isCustom ? 'bg-slate-800 text-blue-400 font-bold' : 'text-slate-500 hover:text-slate-300'}`}
            onClick={() => onChange({ membrane_mode: 'catalog' })}
          >
            Catalog
          </button>
          <div className="w-[1px] bg-slate-800 mx-0.5 my-1"></div>
          <button
            className={`px-2 py-0.5 text-[10px] rounded transition-colors ${isCustom ? 'bg-slate-800 text-emerald-400 font-bold' : 'text-slate-500 hover:text-slate-300'}`}
            onClick={() => onChange({ membrane_mode: 'custom' })}
          >
            Custom
          </button>
        </div>
      </div>

      {/* Catalog 모드: 드롭다운 메뉴 */}
      {!isCustom ? (
        <div className="mb-2">
          <label className={LABEL_CLS}>Select Model</label>
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
                {`[${m.vendor}] ${m.name} (${m.area_m2}m²)`}
              </option>
            ))}
          </select>
        </div>
      ) : (
        // Custom 모드: 안내 문구
        <div className="mb-2 p-2 bg-emerald-900/10 border border-emerald-500/20 rounded text-[10px] text-emerald-400">
          ✨ Custom Mode: You can manually edit the specs below.
        </div>
      )}

      {/* 스펙 입력 폼 (조건부 렌더링) */}
      {isDiffusiveType ? (
        <RoLayout
          isCustom={isCustom}
          area={area}
          A={A}
          B={B}
          rej={rej}
          onChange={onChange}
        />
      ) : (
        <UfLayout isCustom={isCustom} area={area} A={A} onChange={onChange} />
      )}
    </div>
  );
};

export default MembraneSelect;
