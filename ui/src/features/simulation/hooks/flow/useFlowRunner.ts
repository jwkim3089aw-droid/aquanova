// ui/src/features/simulation/hooks/flow/useFlowRunner.ts
import { useCallback, useRef } from 'react';
import { runSimulation } from '@/api/simulation';
import type { SimulationRequest, FeedInput as ApiFeedInput } from '@/api/types';
import {
  UnitMode,
  ChainOk,
  ChainErr,
  UnitNodeRF,
  UnitKind,
} from '../../model/types';
import {
  cryptoRandomId,
  buildLinearChain,
  makeLinearEdges,
  convertROutToDisplay,
  applyStageChips,
  toStagePayload,
  resolveProjectId,
} from '../../model/logic';
import { mapChemistryToBackend } from './utils';
// 프론트엔드 데이터베이스 카탈로그 임포트
import { getFallbackMembrane } from '../../data/membrane_catalog';
import { readPrecisionModeEnabled } from '../../precisionMode';




export function useFlowRunner(props: {
  nodes: any[];
  edges: any[];
  feed: any;
  feedChemistry: any;
  unitMode: UnitMode;
  scenarioName: string;
  optSegments: number;
  optPumpEff: number;
  optErdEff: number;
  opexConfig: any;
  pushToast: (m: string) => void;
  setNodes: Function;
  setEdges: Function;
  setLoading: Function;
  setErr: Function;
  setData: Function;
  setChemSummary: Function;
}) {
  const {
    nodes,
    edges,
    feed,
    feedChemistry,
    unitMode,
    scenarioName,
    optSegments,
    optPumpEff,
    optErdEff,
    opexConfig,
    pushToast,
    setNodes,
    setEdges,
    setLoading,
    setErr,
    setData,
    setChemSummary,
  } = props;

  // 동시 실행 방지 플래그
  const isRunningRef = useRef(false);

  const onRun = useCallback(async () => {
    if (isRunningRef.current) {
      console.warn('Simulation is already running. Please wait.');
      return;
    }

    isRunningRef.current = true;
    setLoading(true);
    setErr(null);
    setData(null);
    setChemSummary(null);

    try {
      let check = buildLinearChain(nodes, edges) as ChainOk | ChainErr;

      // 자동 복구 로직
      if (!check.ok) {
        const hypot = makeLinearEdges(nodes);
        const check2 = buildLinearChain(nodes, hypot);
        if (check2.ok) {
          setEdges(() => hypot);
          check = check2 as ChainOk;
        } else {
          throw new Error(
            (check2 as ChainErr).message ?? '유효한 공정 순서를 구성해주세요.',
          );
        }
      }

      const unitNodes = (check as ChainOk).chain as UnitNodeRF[];
      const stageChain = unitNodes.filter(
        (n) => ((n.data as any).kind as UnitKind) !== 'PUMP',
      );
      if (stageChain.length === 0)
        throw new Error(
          '시뮬레이션할 스테이지(공정)가 최소 1개 이상 필요합니다.',
        );

      const { chemistry, ions } = mapChemistryToBackend(feedChemistry);
      const feedSI: ApiFeedInput = {
        flow_m3h: feed.flow_m3h,
        tds_mgL: feed.tds_mgL,
        temperature_C: feed.temperature_C,
        ph: feed.ph,
        pressure_bar: feed.pressure_bar ?? 0.0,
        water_type: feed.water_type ?? null,
        temp_min_C: feed.temp_min_C ?? null,
        temp_max_C: feed.temp_max_C ?? null,
        fouling: feed.fouling,
        ions: ions ?? undefined,
      };

      const globals = { defaultMembraneModel: 'AUTO', pumpEff: optPumpEff };

      // 카탈로그 기반 물리 보정 계수 병합
      const stagesPayload = stageChain
        .flatMap((n) => toStagePayload(n, unitMode, globals))
        .map((stage) => {
          if (stage.cfg && stage.cfg.membrane_model) {
            const spec = getFallbackMembrane(stage.cfg.membrane_model);
            if (spec) {
              stage.cfg.membrane_A_lmh_bar =
                spec.A_lmh_bar ?? stage.cfg.membrane_A_lmh_bar;
              stage.cfg.membrane_B_lmh = spec.B_lmh ?? stage.cfg.membrane_B_lmh;
              stage.cfg.A_correction_factor =
                spec.A_correction_factor ?? stage.cfg.A_correction_factor;
              stage.cfg.B_correction_factor =
                spec.B_correction_factor ?? stage.cfg.B_correction_factor;
              stage.cfg.temp_corr_factor_A =
                spec.temp_corr_factor_A ?? stage.cfg.temp_corr_factor_A;
              stage.cfg.temp_corr_factor_B =
                spec.temp_corr_factor_B ?? stage.cfg.temp_corr_factor_B;
              stage.cfg.fouling_factor =
                spec.fouling_factor ?? stage.cfg.fouling_factor;
              stage.cfg.dp_per_elem_bar =
                spec.dp_per_elem_bar ?? stage.cfg.dp_per_elem_bar;
              stage.cfg.cp_adjustment_factor =
                spec.cp_adjustment_factor ?? stage.cfg.cp_adjustment_factor;
              stage.cfg.pump_efficiency = optPumpEff ?? 0.8;
            }
          }
          return stage;
        });

      const precisionModeEnabled = readPrecisionModeEnabled();
      const payload: SimulationRequest = {
        simulation_id: cryptoRandomId(),
        project_id: resolveProjectId(),
        precision_mode_enabled: precisionModeEnabled,
        engine_mode: precisionModeEnabled ? 'precision' : 'raw',
        scenario_name: scenarioName,
        feed: feedSI,
        stages: stagesPayload,
        options: {
          segments: optSegments,
          pump_eff: optPumpEff,
          erd_eff: optErdEff,
        },
        chemistry: chemistry ?? null,
        opex_config: opexConfig,
      };

      const output = await runSimulation(payload);
      const outDisp = convertROutToDisplay(output as any, unitMode);
      const outDispWithPrecision = {
        ...outDisp,
        precision_report: output.precision_report ?? null,
      };

      setData(outDispWithPrecision);
      setChemSummary((output as any).chemistry ?? null);

      applyStageChips(
        stageChain.map((n) => n.id),
        (outDisp as any)?.stage_metrics ?? null,
        (outDisp as any)?.kpi ?? null,
        unitMode,
        setNodes as any,
      );

      pushToast('시뮬레이션 완료');
    } catch (e: any) {
      console.error('❌ Simulation Error:', e);

      let msg = '시뮬레이션 중 알 수 없는 오류가 발생했습니다.';
      if (e?.response?.data?.detail) {
        const detail = e.response.data.detail;
        msg = Array.isArray(detail)
          ? JSON.stringify(detail, null, 2)
          : String(detail);
      } else if (e?.message) {
        msg = e.message;
      }
      setErr(msg);
    } finally {
      isRunningRef.current = false;
      setLoading(false);
    }
  }, [
    nodes,
    edges,
    feed,
    feedChemistry,
    unitMode,
    scenarioName,
    optSegments,
    optPumpEff,
    optErdEff,
    opexConfig,
    pushToast,
    setNodes,
    setEdges,
    setLoading,
    setErr,
    setData,
    setChemSummary,
  ]);

  return { onRun };
}
