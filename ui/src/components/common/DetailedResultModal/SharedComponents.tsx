// ui/src/components/common/DetailedResultModal/SharedComponents.tsx
import React from 'react';
import { ChevronRight, CheckCircle2, AlertCircle } from 'lucide-react';
import { fmt } from '../../../features/simulation/model/types';
import { STYLES } from './constants';

export function SidebarBtn({ active, onClick, icon: Icon, label, badge }: any) {
  return (
    <button
      onClick={onClick}
      className={`mx-3 mb-1 flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-medium transition-all group ${
        active
          ? 'bg-blue-600 text-white shadow-md shadow-blue-900/30'
          : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
      }`}
    >
      <Icon
        className={`w-4 h-4 transition-colors ${
          active ? 'text-white' : 'text-slate-500 group-hover:text-slate-300'
        }`}
      />
      <span className="flex-1 text-left">{label}</span>
      {badge && (
        <span
          className={`text-[9px] px-1.5 py-0.5 rounded font-bold tracking-wide ${
            active
              ? 'bg-blue-500 text-blue-100 border border-blue-400'
              : 'bg-slate-800 text-slate-400 border border-slate-700'
          }`}
        >
          {badge}
        </span>
      )}
      {active && <ChevronRight className="w-3 h-3 ml-auto opacity-80" />}
    </button>
  );
}

export function TabBtn({ active, onClick, icon: Icon, label }: any) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-5 py-3 text-xs font-bold transition-all border-b-[2px] outline-none whitespace-nowrap ${
        active
          ? 'border-blue-500 text-blue-400 bg-slate-800/50'
          : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-800/30'
      }`}
    >
      <Icon className="w-4 h-4" /> {label}
    </button>
  );
}

export function Row({ label, icon, color, flow, tds, press }: any) {
  return (
    <tr className="hover:bg-slate-800/30 transition-colors group">
      <td className={`${STYLES.TD_L} pl-5 ${color}`}>
        <div className="flex items-center gap-2 font-bold">
          <div className="opacity-70 group-hover:opacity-100 transition-opacity">
            {icon}
          </div>{' '}
          {label}
        </div>
      </td>
      <td className={STYLES.TD}>{fmt(flow)}</td>
      <td className={STYLES.TD}>{fmt(tds)}</td>
      <td className={STYLES.TD}>{fmt(press)}</td>
    </tr>
  );
}

export function BigKPI({
  label,
  value,
  unit,
  icon: Icon,
  color,
  subValue,
}: any) {
  const map: any = {
    blue: 'text-blue-400 from-blue-500/10 to-blue-500/5 border-blue-500/20',
    emerald:
      'text-emerald-400 from-emerald-500/10 to-emerald-500/5 border-emerald-500/20',
    yellow:
      'text-yellow-400 from-yellow-500/10 to-yellow-500/5 border-yellow-500/20',
  };
  return (
    <div
      className={`p-5 rounded-xl border bg-gradient-to-br shadow-sm relative overflow-hidden group transition-all duration-300 ${map[color]}`}
    >
      <div className="absolute -top-6 -right-6 p-6 opacity-5 group-hover:opacity-10 group-hover:scale-110 transition-transform duration-500 bg-current rounded-full">
        <Icon className="w-20 h-20" />
      </div>
      <div className="flex items-center gap-2 mb-2 relative z-10">
        <Icon className="w-4 h-4 opacity-70" />
        <span className="text-xs font-bold uppercase tracking-wider opacity-90">
          {label}
        </span>
      </div>
      <div className="flex items-baseline gap-1 relative z-10">
        <span className="text-3xl font-mono font-bold tracking-tighter drop-shadow-sm">
          {fmt(value)}
        </span>
        <span className="text-xs font-bold opacity-80">{unit}</span>
      </div>
      {subValue && (
        <div className="mt-3 text-[10px] font-medium opacity-80 flex items-center gap-1.5 relative z-10">
          <div className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />{' '}
          {subValue}
        </div>
      )}
    </div>
  );
}

export function MiniKPI({ label, value, unit }: any) {
  return (
    <div className="p-4 rounded-lg border border-slate-700 bg-slate-800/50 hover:bg-slate-800/80 transition-colors">
      <div className="text-[10px] text-slate-400 font-bold uppercase mb-1">
        {label}
      </div>
      <div className="text-lg font-mono font-bold text-slate-100">
        {value}{' '}
        <span className="text-[10px] text-slate-400 ml-0.5">{unit}</span>
      </div>
    </div>
  );
}

export function ChemCard({ title, color, data }: any) {
  const headerColor = color === 'blue' ? 'bg-blue-500' : 'bg-orange-500';
  return (
    <div className="bg-slate-900 border border-slate-700 rounded-sm overflow-hidden shadow-md">
      <div className="bg-slate-800 px-6 py-4 border-b border-slate-700 flex items-center gap-2">
        <span className={`w-2 h-2 rounded-full ${headerColor}`}></span>
        <h4 className="font-bold text-slate-100">{title}</h4>
      </div>
      <div className="p-6 space-y-5">
        <ChemRow
          label="LSI (Langelier)"
          value={data.lsi}
          desc="탄산칼슘 스케일 지표 (CaCO3 Potential)"
          threshold={0}
          type="max"
        />
        <ChemRow
          label="RSI (Ryznar)"
          value={data.rsi}
          desc="부식 및 스케일성 지표 (Corrosion vs Scaling)"
          threshold={6}
          type="min"
        />
        <ChemRow
          label="S&DSI (Stiff-Davis)"
          value={data.s_dsi}
          desc="고농도 스케일 지표 (High TDS Scaling)"
          threshold={0}
          type="max"
        />
        <div className="border-t border-slate-700/80 pt-5 mt-5 space-y-5">
          <ChemRow
            label="황산칼슘 (CaSO4 Saturation)"
            value={data.caso4_si ?? data.caso4_sat_pct}
            unit="%"
            desc="황산칼슘(석고) 포화도 (Gypsum Potential)"
            threshold={100}
            type="max"
          />
          <ChemRow
            label="실리카 (SiO2 Saturation)"
            value={data.sio2_si ?? data.sio2_sat_pct}
            unit="%"
            desc="실리카 포화도 (Silica Potential)"
            threshold={100}
            type="max"
          />
        </div>
      </div>
    </div>
  );
}

export function ChemRow({
  label,
  value,
  unit = '',
  desc,
  threshold,
  type,
}: any) {
  if (value === undefined || value === null) return null;
  let isSafe = true;
  if (type === 'max' && value > threshold) isSafe = false;
  if (type === 'min' && value < threshold) isSafe = false;

  return (
    <div className="flex items-center justify-between group py-1">
      <div>
        {/* 라벨: slate-400 -> slate-200, 크기도 살짝 키움 */}
        <div className="text-sm font-bold text-slate-200">{label}</div>
        {/* 설명: slate-600 -> slate-400으로 가독성 대폭 상향 */}
        <div className="text-[11px] text-slate-400 mt-1">{desc}</div>
      </div>
      <div className="text-right flex items-center gap-3">
        {/* 수치: 글씨 크기 키우고 대비 상향 */}
        <div
          className={`text-base font-mono font-bold ${isSafe ? 'text-emerald-400' : 'text-rose-400'}`}
        >
          {Number(value).toFixed(2)}{' '}
          <span className="text-xs opacity-80">{unit}</span>
        </div>
        {/* 아이콘 크기 살짝 키움 */}
        {isSafe ? (
          <CheckCircle2 className="w-4 h-4 text-emerald-500" />
        ) : (
          <AlertCircle className="w-4 h-4 text-rose-500" />
        )}
      </div>
    </div>
  );
}
