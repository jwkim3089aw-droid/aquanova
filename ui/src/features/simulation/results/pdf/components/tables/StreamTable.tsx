// ui/src/features/simulation/results/pdf/components/tables/StreamTable.tsx
import React from 'react';
import { fmt } from '../../utils';
import { UnitLabels } from '../../types';

// 안전하게 이온 데이터를 추출하고 소수점 2자리로 맞추는 헬퍼 함수
const getIon = (stream: any, ionName: string) => {
  const val = stream?.ions?.[ionName] || stream?.ions?.[ionName.toLowerCase()];
  return typeof val === 'number' ? val.toFixed(2) : '0.00';
};

export function StreamTable({
  feed,
  perm,
  brine,
  u,
}: {
  feed: any;
  perm: any;
  brine: any;
  u: UnitLabels;
}) {
  // WAVE 스타일의 밀도 높고 딱 떨어지는 테두리 디자인
  const thClass =
    'py-1.5 px-3 text-[11px] font-bold text-slate-800 border border-slate-400 bg-slate-200 text-center';
  const tdLabelClass =
    'py-1 px-3 text-[11px] font-semibold text-slate-700 border border-slate-300 bg-slate-50';
  const tdValueClass =
    'py-1 px-3 text-[11px] text-right tabular-nums text-slate-800 border border-slate-300';
  const sectionHeaderClass =
    'py-1 px-3 text-[11px] font-bold text-slate-900 bg-slate-100 border border-slate-300 text-left tracking-wide';

  // 기본 행 렌더링 함수
  const renderRow = (
    label: string,
    feedVal: any,
    permVal: any,
    brineVal: any,
  ) => (
    <tr key={label} className="hover:bg-slate-50/50">
      <td className={tdLabelClass}>{label}</td>
      <td className={tdValueClass}>{feedVal}</td>
      <td className={tdValueClass}>{permVal}</td>
      <td className={tdValueClass}>{brineVal}</td>
    </tr>
  );

  // 이온 행 렌더링 함수 (값이 모두 0인 이온은 숨겨서 표를 깔끔하게 유지)
  const renderIonRow = (ion: string, label: string) => {
    const f = getIon(feed, ion);
    const p = getIon(perm, ion);
    const b = getIon(brine, ion);

    // Feed, Perm, Brine 모두 0.00이면 렌더링하지 않음 (스마트 필터링)
    if (f === '0.00' && p === '0.00' && b === '0.00') return null;

    return renderRow(label, f, p, b);
  };

  return (
    <div className="w-full print:break-inside-avoid">
      <table className="w-full border-collapse border-2 border-slate-500">
        <thead>
          <tr>
            <th className={thClass} style={{ width: '28%' }}>
              스트림 속성 (Stream Properties)
            </th>
            <th className={thClass} style={{ width: '24%' }}>
              유입수 (Feed)
            </th>
            <th className={thClass} style={{ width: '24%' }}>
              생산수 (Permeate)
            </th>
            <th className={thClass} style={{ width: '24%' }}>
              농축수 (Concentrate)
            </th>
          </tr>
        </thead>
        <tbody>
          {/* 1. 기본 속성 섹션 */}
          {renderRow(
            `유량 (Flow, ${u.flow || 'm³/h'})`,
            fmt(feed?.flow_m3h),
            fmt(perm?.flow_m3h),
            fmt(brine?.flow_m3h),
          )}
          {renderRow(
            `압력 (Pressure, ${u.pressure || 'bar'})`,
            fmt(feed?.pressure_bar),
            fmt(perm?.pressure_bar),
            fmt(brine?.pressure_bar),
          )}
          {renderRow(
            '온도 (Temperature, °C)',
            fmt(feed?.temperature_C),
            fmt(perm?.temperature_C),
            fmt(brine?.temperature_C),
          )}
          {renderRow(
            'pH',
            fmt(feed?.ph, 2),
            fmt(perm?.ph, 2),
            fmt(brine?.ph, 2),
          )}
          {renderRow(
            '총 용존 고형물 (TDS, mg/L)',
            fmt(feed?.tds_mgL),
            fmt(perm?.tds_mgL),
            fmt(brine?.tds_mgL),
          )}

          {/* 2. 양이온 섹션 */}
          <tr>
            <td colSpan={4} className={sectionHeaderClass}>
              양이온 (Cations, mg/L)
            </td>
          </tr>
          {renderIonRow('Na', '나트륨 (Na)')}
          {renderIonRow('K', '칼륨 (K)')}
          {renderIonRow('Mg', '마그네슘 (Mg)')}
          {renderIonRow('Ca', '칼슘 (Ca)')}
          {renderIonRow('Ba', '바륨 (Ba)')}
          {renderIonRow('Sr', '스트론튬 (Sr)')}
          {renderIonRow('NH4', '암모늄 (NH4)')}

          {/* 3. 음이온 섹션 */}
          <tr>
            <td colSpan={4} className={sectionHeaderClass}>
              음이온 (Anions, mg/L)
            </td>
          </tr>
          {renderIonRow('Cl', '염소 (Cl)')}
          {renderIonRow('SO4', '황산 (SO4)')}
          {renderIonRow('HCO3', '중탄산 (HCO3)')}
          {renderIonRow('CO3', '탄산 (CO3)')}
          {renderIonRow('NO3', '질산 (NO3)')}
          {renderIonRow('F', '불소 (F)')}

          {/* 4. 중성 물질 섹션 */}
          <tr>
            <td colSpan={4} className={sectionHeaderClass}>
              중성 물질 (Neutrals, mg/L)
            </td>
          </tr>
          {renderIonRow('SiO2', '실리카 (SiO2)')}
          {renderIonRow('CO2', '이산화탄소 (CO2)')}
          {renderIonRow('B', '붕소 (B)')}
        </tbody>
      </table>
    </div>
  );
}
