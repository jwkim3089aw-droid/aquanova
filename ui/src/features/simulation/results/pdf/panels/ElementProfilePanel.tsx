// ui/src/features/simulation/results/pdf/panels/ElementProfilePanel.tsx
import React from 'react';
import {
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';
import { AutoSizedChart, JsonDetails } from '../components';
import {
  fmt,
  pct,
  pickAnyFromKeys,
  pickNumFromKeys,
  safeArr,
  safeObj,
} from '../utils';
import { UnitLabels } from '../types';

export function ElementProfilePanel({
  elementProfile,
  u,
}: {
  elementProfile: any[];
  u: UnitLabels;
}) {
  const ep = safeArr(elementProfile);
  if (!ep.length) {
    return (
      <div className="text-[10px] text-slate-500 italic">
        엘리먼트 프로파일 데이터가 없습니다 (No element profile).
      </div>
    );
  }

  const columns: Array<{
    key: string;
    label: string;
    unit?: string;
    num?: boolean;
    candidates?: string[];
  }> = [
    { key: 'idx', label: 'Elem' },
    {
      key: 'flux',
      label: 'Flux',
      unit: u.flux,
      num: true,
      candidates: ['flux_lmh', 'jw_lmh', 'jw', 'flux', 'Jw'],
    },
    {
      key: 'ndp',
      label: 'NDP',
      unit: u.pressure,
      num: true,
      candidates: ['ndp_bar', 'ndp', 'NDP'],
    },
    {
      key: 'p',
      label: 'Pressure',
      unit: u.pressure,
      num: true,
      candidates: ['pressure_bar', 'p_bar', 'p', 'P'],
    },
    {
      key: 'tds',
      label: 'TDS',
      unit: 'mg/L',
      num: true,
      candidates: ['tds_mgL', 'tds', 'TDS', 'cp_mgL', 'Cp'],
    },
    {
      key: 'rec',
      label: 'Recovery',
      unit: '%',
      num: true,
      candidates: ['recovery_pct', 'rec_pct', 'recovery', 'Recovery'],
    },
  ];

  const rows = ep.map((e, i) => {
    const obj = safeObj(e);
    const idx =
      pickAnyFromKeys(obj, [
        'idx',
        'i',
        'element',
        'element_no',
        'elem',
        'n',
      ]) ?? i + 1;

    const flux = pickNumFromKeys(obj, columns[1].candidates || []);
    const ndp = pickNumFromKeys(obj, columns[2].candidates || []);
    const p = pickNumFromKeys(obj, columns[3].candidates || []);
    const tds = pickNumFromKeys(obj, columns[4].candidates || []);
    const rec = pickNumFromKeys(obj, columns[5].candidates || []);

    return { idx, flux, ndp, p, tds, rec, __raw: obj };
  });

  const has = {
    flux: rows.some((r) => r.flux != null),
    ndp: rows.some((r) => r.ndp != null),
    p: rows.some((r) => r.p != null),
    tds: rows.some((r) => r.tds != null),
    rec: rows.some((r) => r.rec != null),
  };

  const head = rows.slice(0, Math.min(12, rows.length));
  const tail = rows.length > 24 ? rows.slice(-12) : rows.slice(12);

  const chartData = rows.map((r, i) => ({
    i: i + 1,
    flux: r.flux ?? null,
    ndp: r.ndp ?? null,
  }));
  const hasFlux = chartData.some((d) => d.flux != null);
  const hasNdp = chartData.some((d) => d.ndp != null);

  // 💡 명품 Slate 테마 오버라이드
  const tableClass = 'w-full border-collapse border-2 border-slate-500';
  const thClass =
    'py-1.5 px-2 text-[10px] font-bold text-slate-800 border border-slate-400 bg-slate-200 text-center';
  const tdClass =
    'py-1 px-2 text-[10px] text-slate-900 border border-slate-300 text-center tabular-nums';
  const tdLabelClass =
    'py-1 px-2 text-[10px] font-bold text-slate-700 border border-slate-300 bg-slate-50 text-center';

  const Table = ({ part, title }: { part: any[]; title: string }) => (
    <div className="mt-4 print:break-inside-avoid">
      <div className="text-[11px] font-bold text-slate-800 mb-2 pl-2 border-l-2 border-slate-800 uppercase tracking-wider">
        {title}
      </div>
      <table className={tableClass}>
        <thead>
          <tr>
            <th className={thClass}>Elem</th>
            {has.flux ? (
              <th className={thClass}>{`Flux (${u.flux})`}</th>
            ) : null}
            {has.ndp ? (
              <th className={thClass}>{`NDP (${u.pressure})`}</th>
            ) : null}
            {has.p ? <th className={thClass}>{`P (${u.pressure})`}</th> : null}
            {has.tds ? <th className={thClass}>TDS (mg/L)</th> : null}
            {has.rec ? <th className={thClass}>Rec (%)</th> : null}
          </tr>
        </thead>
        <tbody>
          {part.map((r, i) => (
            <tr key={i} className="hover:bg-slate-50/50">
              <td className={tdLabelClass}>{String(r.idx)}</td>
              {has.flux ? <td className={tdClass}>{fmt(r.flux)}</td> : null}
              {has.ndp ? <td className={tdClass}>{fmt(r.ndp)}</td> : null}
              {has.p ? <td className={tdClass}>{fmt(r.p)}</td> : null}
              {has.tds ? <td className={tdClass}>{fmt(r.tds)}</td> : null}
              {has.rec ? (
                <td className={tdClass}>{r.rec == null ? '-' : pct(r.rec)}</td>
              ) : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  return (
    <div className="space-y-4">
      {/* 💡 차트 영역도 Slate 테마에 맞춰 테두리 강화 */}
      {hasFlux || hasNdp ? (
        <div className="print:break-inside-avoid">
          <div className="text-[11px] font-bold text-slate-800 mb-2 pl-2 border-l-2 border-slate-800 uppercase tracking-wider">
            프로파일 차트 (Element Profile Chart)
          </div>
          <AutoSizedChart className="h-56 rounded border border-slate-400 bg-white p-2 min-w-0 min-h-0 shadow-sm">
            {({ width, height }) => (
              <ComposedChart
                width={width}
                height={height}
                data={chartData}
                margin={{ top: 10, right: 12, bottom: 10, left: 10 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#cbd5e1" />
                <XAxis dataKey="i" tick={{ fontSize: 10 }} stroke="#64748b" />
                <YAxis
                  yAxisId="left"
                  tick={{ fontSize: 10 }}
                  width={34}
                  stroke="#3b82f6"
                />
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  tick={{ fontSize: 10 }}
                  width={34}
                  stroke="#10b981"
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#ffffff',
                    borderColor: '#cbd5e1',
                    fontSize: '10px',
                    borderRadius: '4px',
                  }}
                />
                {hasFlux ? (
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey="flux"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    dot={{ r: 2, fill: '#3b82f6' }}
                    isAnimationActive={false}
                    name={`Flux (${u.flux})`}
                  />
                ) : null}
                {hasNdp ? (
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="ndp"
                    stroke="#10b981"
                    strokeWidth={2}
                    dot={{ r: 2, fill: '#10b981' }}
                    isAnimationActive={false}
                    name={`NDP (${u.pressure})`}
                  />
                ) : null}
              </ComposedChart>
            )}
          </AutoSizedChart>
        </div>
      ) : null}

      <Table part={head} title={`데이터 표 (처음 ${head.length}개 엘리먼트)`} />
      {tail.length ? (
        <Table
          part={tail}
          title={`데이터 표 (마지막 ${tail.length}개 엘리먼트)`}
        />
      ) : null}

      <div className="text-[9px] text-slate-500 italic mt-2">
        * 존재하는 컬럼만 자동으로 표시되며, 최대 24개의 엘리먼트 데이터가
        요약dho 출력됩니다.
      </div>
    </div>
  );
}
