import React from "react";
import { NavLink } from "react-router-dom";

export default function Header() {
  return (
    <header className="flex h-[52px] items-center gap-4 border-b border-slate-800 bg-slate-950 px-4 text-sm font-medium text-slate-100 shadow-sm z-50">
      
      {/* 로고 섹션: public/brand/logo.png 사용 */}
      <div className="flex items-center gap-2 mr-2">
        <img 
          src="/brand/logo.png" 
          alt="AquaNova Logo" 
          className="h-12 w-auto object-contain"
        />
      </div>

      <nav className="flex items-center gap-1">
        <NavLink
          to="/"
          className={({ isActive }) =>
            `px-3 py-1.5 rounded-md text-xs transition-all duration-200 ${
              isActive
                ? "bg-slate-800 text-sky-400 font-semibold shadow-inner border border-slate-700/50"
                : "text-slate-400 hover:text-slate-100 hover:bg-slate-800/50"
            }`
          }
        >
          Flow Builder
        </NavLink>
        <NavLink
          to="/reports"
          className={({ isActive }) =>
            `px-3 py-1.5 rounded-md text-xs transition-all duration-200 ${
              isActive
                ? "bg-slate-800 text-sky-400 font-semibold shadow-inner border border-slate-700/50"
                : "text-slate-400 hover:text-slate-100 hover:bg-slate-800/50"
            }`
          }
        >
          Reports
        </NavLink>
      </nav>

      <div className="ml-auto flex items-center gap-3">
        <div className="flex items-center gap-1.5 text-[10px] bg-slate-900 px-2 py-1 rounded border border-slate-800 text-slate-400">
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></div>
          <span>Connected</span>
        </div>
      </div>
    </header>
  );
}