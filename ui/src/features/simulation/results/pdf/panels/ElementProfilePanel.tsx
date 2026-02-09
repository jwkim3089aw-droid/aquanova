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
import { THEME } from '../theme';
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
      <div className="text-[10px] text-slate-500">No element profile.</div>
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

  const Table = ({ part, title }: { part: any[]; title: string }) => (
    <div className="mt-3">
      <div className="text-[10px] font-extrabold text-slate-500 uppercase tracking-widest mb-2">
        {title}
      </div>
      <div className={THEME.TABLE_WRAP}>
        <div className="overflow-x-auto">
          <table className={THEME.TABLE}>
            <thead>
              <tr>
                <th className={THEME.TH}>Elem</th>
                {has.flux ? (
                  <th className={THEME.TH}>{`Flux (${u.flux})`}</th>
                ) : null}
                {has.ndp ? (
                  <th className={THEME.TH}>{`NDP (${u.pressure})`}</th>
                ) : null}
                {has.p ? (
                  <th className={THEME.TH}>{`P (${u.pressure})`}</th>
                ) : null}
                {has.tds ? <th className={THEME.TH}>TDS (mg/L)</th> : null}
                {has.rec ? <th className={THEME.TH}>Rec (%)</th> : null}
              </tr>
            </thead>
            <tbody>
              {part.map((r, i) => (
                <tr key={i} className={THEME.TR}>
                  <td className={THEME.TD_LABEL}>{String(r.idx)}</td>
                  {has.flux ? (
                    <td className={THEME.TD}>{fmt(r.flux)}</td>
                  ) : null}
                  {has.ndp ? <td className={THEME.TD}>{fmt(r.ndp)}</td> : null}
                  {has.p ? <td className={THEME.TD}>{fmt(r.p)}</td> : null}
                  {has.tds ? <td className={THEME.TD}>{fmt(r.tds)}</td> : null}
                  {has.rec ? (
                    <td className={THEME.TD}>
                      {r.rec == null ? '-' : pct(r.rec)}
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );

  return (
    <div className="space-y-3">
      {hasFlux || hasNdp ? (
        <AutoSizedChart className="h-56 rounded-xl border border-slate-200 bg-slate-50 p-3 min-w-0 min-h-0">
          {({ width, height }) => (
            <ComposedChart
              width={width}
              height={height}
              data={chartData}
              margin={{ top: 10, right: 12, bottom: 10, left: 10 }}
            >
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="i" tick={{ fontSize: 10 }} />
              <YAxis yAxisId="left" tick={{ fontSize: 10 }} width={34} />
              <YAxis
                yAxisId="right"
                orientation="right"
                tick={{ fontSize: 10 }}
                width={34}
              />
              <Tooltip />
              {hasFlux ? (
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="flux"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={false}
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
                  dot={false}
                  isAnimationActive={false}
                  name={`NDP (${u.pressure})`}
                />
              ) : null}
            </ComposedChart>
          )}
        </AutoSizedChart>
      ) : (
        <div className="text-[10px] text-slate-500">
          Element profile 차트에 필요한 flux/ndp 데이터가 없습니다.
        </div>
      )}

      <Table part={head} title={`Element Profile (처음 ${head.length}개)`} />
      {tail.length ? (
        <Table
          part={tail}
          title={`Element Profile (마지막 ${tail.length}개)`}
        />
      ) : null}

      <div className="text-[10px] text-slate-500">
        * Wave Detailed의 element-level 감성을 위해, elementProfile을 “존재하는
        컬럼만 자동 표시”로 구성했습니다.
      </div>

      <JsonDetails
        titleKo="Raw Element Profile (접기)"
        obj={ep}
        maxChars={12000}
      />
    </div>
  );
}
