// ui/src/features/simulation/editors/UnitForms/MFEditor.tsx

import React from 'react';
import MembraneSelect from '../../components/MembraneSelect';
import { mapMembraneChange } from './utils';

export function MFEditor({ node, onChange }: any) {
  const cfg = node.cfg || {};
  return (
    <div className="space-y-3 p-4">
      <MembraneSelect
        unitType="MF"
        mode={cfg.membrane_mode}
        area={cfg.custom_area_m2 ?? cfg.membrane_area_m2}
        A={cfg.custom_A_lmh_bar ?? cfg.membrane_A_lmh_bar}
        onChange={(u: any) => onChange({ ...cfg, ...mapMembraneChange(u) })}
      />
      <div className="text-xs text-slate-400 mt-2">
        * 상세 설정 폼은 추후 확장 예정입니다.
      </div>
    </div>
  );
}
