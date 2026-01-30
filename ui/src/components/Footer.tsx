// ui/src/components/Footer.tsx

import React from "react";

export default function Footer() {
  // [NEW] 현재 시스템 연도를 자동으로 가져옵니다.
  const currentYear = new Date().getFullYear();

  return (
    <footer className="h-[32px] bg-slate-950 border-t border-slate-800 flex items-center justify-between px-4 text-[10px] text-slate-500 select-none shrink-0 z-40 relative">
      {/* Left: System Status & Version */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="font-bold text-slate-400 tracking-wide">AQUANOVA</span>
        </div>
        
        <div className="h-3 w-px bg-slate-800"></div>

        <div className="flex items-center gap-2">
          <span className="text-slate-500">v2.5.0</span>
          <span className="flex items-center gap-1.5 px-1.5 py-0.5 rounded bg-slate-900/50 border border-slate-800/50">
            <span className="relative flex h-1.5 w-1.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500"></span>
            </span>
            <span className="text-emerald-500/90 font-medium">Ready</span>
          </span>
        </div>
      </div>

      {/* Right: Technical Info & Copyright */}
      <div className="flex items-center gap-6">
        <div className="hidden md:flex items-center gap-4 opacity-60 hover:opacity-100 transition-opacity duration-300">
          <div className="flex items-center gap-1.5 cursor-help" title="Backend Server Status">
            <div className="w-1.5 h-1.5 rounded-full bg-blue-500"></div>
            <span>API: 8003</span>
          </div>
          <div className="flex items-center gap-1.5 cursor-help" title="Frontend Server Status">
            <div className="w-1.5 h-1.5 rounded-full bg-indigo-500"></div>
            <span>UI: 5174</span>
          </div>
        </div>
        
        <div className="h-3 w-px bg-slate-800 hidden md:block"></div>
        
        {/* [CHANGED] 2025 -> {currentYear} 변수 적용 */}
        <span className="text-slate-600">© {currentYear} AquaWorks Corp.</span>
      </div>
    </footer>
  );
}