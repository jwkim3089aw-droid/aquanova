import {
  expect,
  test,
  type APIResponse,
  type Page,
} from '@playwright/test';

const SESSION_KEY = 'AQUANOVA_SESSION_V1';

interface HRROStagePayload {
  module_type?: string;
  membrane_model?: string;
  pf_mode?: string;
  brine_valve_mode?: string;
  pf_feed_ratio_pct?: number;
  pf_recovery_pct?: number;
  cc_recycle_m3h_per_pv?: number;
  p3_recycle_capacity_m3h_per_pv?: number;
  hpp_count?: number;
}

interface HRRORunPayload {
  stages: HRROStagePayload[];
}

interface CCROCycle {
  pf_mode: string;
  brine_valve_mode: string;
  pf_feed_ratio_pct: number;
  pf_recovery_pct: number;

  pf_feed_flow_m3h_per_pv: number;
  pf_permeate_flow_m3h_per_pv: number;
  pf_p3_recycle_flow_m3h_per_pv: number;
  pf_membrane_total_feed_flow_m3h_per_pv: number;
  pf_membrane_concentrate_out_m3h_per_pv: number;
  pf_external_drain_setpoint_m3h_per_pv: number;

  p3_required: boolean;
  p3_recycle_capacity_ok: boolean;
  crossflow_ok: boolean;
  partial_drain_mass_balance_ok: boolean;
  p2_oversizing_required: boolean;
  slow_flush_or_poor_salt_displacement: boolean;
}

interface HRROStageResult {
  module_type: string;
  recovery_pct: number;
  chemistry?: {
    ccro_cycle?: CCROCycle;
  };
  time_history?: Array<{
    phase?: string;
  }>;
}

interface HRROSimulationResponse {
  stage_metrics?: HRROStageResult[];
}

function sessionState() {
  return {
    unitMode: 'SI',
    scenarioName: 'V136 HRRO fullstack E2E',

    feed: {
      flow_m3h: 2.02,
      tds_mgL: 412.4,
      temperature_C: 25,
      ph: 6.5,
      pressure_bar: 0,
      water_type: 'Well Water (SDI < 3)',
    },

    nodes: [
      {
        id: 'feed',
        type: 'endpoint',
        position: {
          x: 40,
          y: 160,
        },
        data: {
          type: 'endpoint',
          role: 'feed',
          label: 'Feed',
        },
      },
      {
        id: 'hrro-stage-1',
        type: 'unit',
        position: {
          x: 420,
          y: 160,
        },
        data: {
          type: 'unit',
          kind: 'HRRO',
          label: 'HRRO Stage',
          cfg: {
            module_type: 'HRRO',
            membrane_mode: 'catalog',
            membrane_model: 'filmtec-soar-5000i',

            mode: 'recovery',
            pressure_bar: 50,
            recovery_target_pct: 90,
            stop_recovery_pct: 90,

            element_inch: 8,
            vessel_count: 1,
            elements_per_vessel: 3,
            elements: 3,
            membrane_area_m2: 37.2,

            membrane_A_lmh_bar: 5.5,
            membrane_B_lmh: 0.06,
            membrane_salt_rejection_pct: 99.5,

            flow_factor: 0.85,
            spi: 1,
            permeate_back_pressure_bar: 0,

            loop_volume_m3: 0.09,
            recirc_flow_m3h: 4.5,
            cc_recycle_m3h_per_pv: 4.5,

            timestep_s: 30,
            max_minutes: 60,
            max_tmp_bar: 120,

            /*
             * pf_mode and pf_feed_ratio_pct are intentionally
             * omitted. The product-level AquaNova defaults must
             * add smart_partial_drain + FR150 to the API request.
             */
            pf_recovery_pct: 10,
            p3_recycle_capacity_m3h_per_pv: 3.7,

            adaptive_recovery_enabled: false,
            hpp_sizing_mode: 'base',
            hpp_count: 1,

            p3_generated_head_bar: 0.6,
            p3_casing_pressure_rating_bar: 12,

            mass_transfer: {
              feed_channel_area_m2: 0.0007,
              diffusivity_m2_s: 0.0000000015,
            },

            spacer: {
              thickness_mm: 0.864,
              voidage: 0.9,
              hydraulic_diameter_m: 0.001,
            },
          },
        },
      },
      {
        id: 'product',
        type: 'endpoint',
        position: {
          x: 900,
          y: 160,
        },
        data: {
          type: 'endpoint',
          role: 'product',
          label: 'Product',
        },
      },
    ],

    edges: [
      {
        id: 'feed-to-hrro',
        source: 'feed',
        target: 'hrro-stage-1',
      },
      {
        id: 'hrro-to-product',
        source: 'hrro-stage-1',
        target: 'product',
      },
    ],

    opt: {
      pump_eff: 0.8,
      erd_eff: 0,
      segments: 10,
    },
  };
}

async function prepareScenario(page: Page) {
  await page.addInitScript(
    ({ key, state }) => {
      window.sessionStorage.setItem(
        key,
        JSON.stringify(state),
      );

      window.localStorage.clear();
    },
    {
      key: SESSION_KEY,
      state: sessionState(),
    },
  );

  await page.goto('/');

  await expect(
    page.getByRole('button', {
      name: '실행',
      exact: true,
    }),
  ).toBeVisible();
}

async function executeSimulation(
  page: Page,
): Promise<{
  payload: HRRORunPayload;
  result: HRROSimulationResponse;
  response: APIResponse;
}> {
  const responsePromise = page.waitForResponse(
    (response) =>
      response
        .url()
        .includes('/api/v1/simulation/run')
      && response.request().method() === 'POST',
    {
      timeout: 90_000,
    },
  );

  await page
    .getByRole('button', {
      name: '실행',
      exact: true,
    })
    .click();

  const response = await responsePromise;
  const responseText = await response.text();

  expect(
    response.ok(),
    `HRRO API failed: ${response.status()} ${responseText}`,
  ).toBe(true);

  const payload =
    response.request().postDataJSON() as HRRORunPayload;

  const result =
    JSON.parse(responseText) as HRROSimulationResponse;

  return {
    payload,
    result,
    response,
  };
}

function finiteNumber(
  value: unknown,
  label: string,
): number {
  const number = Number(value);

  expect(
    Number.isFinite(number),
    `${label} must be finite`,
  ).toBe(true);

  return number;
}

function formattedFlow(value: number): string {
  return `${value.toLocaleString('ko-KR', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 3,
  })} m³/h/PV`;
}

test(
  'HRRO smart FR150 runs through the real API and renders the process flow',
  async ({ page }) => {
    await prepareScenario(page);

    const {
      payload,
      result,
      response,
    } = await executeSimulation(page);

    expect(
      new URL(response.url()).origin,
    ).toBe('http://127.0.0.1:5174');

    const requestStage = payload.stages[0];

    expect(requestStage.module_type).toBe('HRRO');
    expect(requestStage.membrane_model).toBe(
      'filmtec-soar-5000i',
    );

    /*
     * These values must be filled by the product UI,
     * not by the backward-compatible backend fallback.
     */
    expect(requestStage.pf_mode).toBe(
      'smart_partial_drain',
    );
    expect(requestStage.pf_feed_ratio_pct).toBe(150);
    expect(requestStage.brine_valve_mode).toBe(
      'partial_pid',
    );
    expect(requestStage.hpp_count).toBe(1);

    const stage = result.stage_metrics?.find(
      (item) =>
        String(item.module_type).toUpperCase()
        === 'HRRO',
    );

    expect(stage).toBeTruthy();

    const cycle = stage?.chemistry?.ccro_cycle;

    expect(cycle).toBeTruthy();

    if (!cycle) {
      throw new Error(
        'Real HRRO response did not include ccro_cycle',
      );
    }

    expect(cycle.pf_mode).toBe(
      'smart_partial_drain',
    );
    expect(cycle.brine_valve_mode).toBe(
      'partial_pid',
    );
    expect(cycle.pf_feed_ratio_pct).toBeCloseTo(
      150,
      6,
    );

    expect(cycle.p3_required).toBe(true);
    expect(cycle.p3_recycle_capacity_ok).toBe(true);
    expect(cycle.crossflow_ok).toBe(true);
    expect(
      cycle.partial_drain_mass_balance_ok,
    ).toBe(true);
    expect(cycle.p2_oversizing_required).toBe(false);
    expect(
      cycle.slow_flush_or_poor_salt_displacement,
    ).toBe(false);

    const pfFeed = finiteNumber(
      cycle.pf_feed_flow_m3h_per_pv,
      'PF feed',
    );

    const product = finiteNumber(
      cycle.pf_permeate_flow_m3h_per_pv,
      'PF product',
    );

    const recycle = finiteNumber(
      cycle.pf_p3_recycle_flow_m3h_per_pv,
      'P-3 recycle',
    );

    const membraneFeed = finiteNumber(
      cycle.pf_membrane_total_feed_flow_m3h_per_pv,
      'membrane total feed',
    );

    const concentrate = finiteNumber(
      cycle.pf_membrane_concentrate_out_m3h_per_pv,
      'membrane concentrate',
    );

    const drain = finiteNumber(
      cycle.pf_external_drain_setpoint_m3h_per_pv,
      'external drain',
    );

    expect(drain).toBeCloseTo(
      pfFeed - product,
      6,
    );

    expect(membraneFeed).toBeCloseTo(
      pfFeed + recycle,
      6,
    );

    expect(concentrate).toBeCloseTo(
      membraneFeed - product,
      6,
    );

    const phases = new Set(
      (stage?.time_history ?? [])
        .map((row) =>
          String(row.phase ?? '').toUpperCase(),
        ),
    );

    expect(phases.has('CC')).toBe(true);
    expect(phases.has('PF')).toBe(true);

    const diagram = page.getByTestId(
      'hrro-process-flow-diagram',
    );

    await diagram.scrollIntoViewIfNeeded();

    await expect(diagram).toBeVisible({
      timeout: 60_000,
    });

    await expect(diagram).toContainText(
      'Smart Partial Drain',
    );
    await expect(diagram).toContainText('FR 150%');
    await expect(diagram).toContainText(
      '운전 조건 정상',
    );

    for (const testId of [
      'hrro-flow-feed',
      'hrro-flow-membrane',
      'hrro-flow-product',
      'hrro-flow-drain',
      'hrro-flow-concentrate',
      'hrro-flow-recycle',
    ]) {
      await expect(
        page.getByTestId(testId),
      ).toBeVisible();
    }

    await expect(
      page.getByTestId('hrro-flow-drain'),
    ).toContainText(
      formattedFlow(drain),
    );

    await expect(
      page.getByTestId('hrro-flow-recycle'),
    ).toContainText(
      formattedFlow(recycle),
    );

    await expect(
      page.getByTestId('hrro-flow-membrane'),
    ).toContainText(
      formattedFlow(membraneFeed),
    );

    await expect(
      page.getByTestId('hrro-phase-status'),
    ).toContainText('PF');

    await expect(
      page.getByTestId('hrro-phase-slider'),
    ).toBeVisible();

    await page
      .getByTestId('hrro-phase-cc')
      .click();

    await expect(
      page.getByTestId('hrro-phase-status'),
    ).toContainText('CC');

    await expect(
      page.getByTestId('hrro-flow-drain'),
    ).toContainText('0 m³/h/PV');

    await expect(
      page.getByTestId('hrro-flow-recycle'),
    ).toContainText('4.5 m³/h/PV');

    await expect(
      page.getByTestId('hrro-flow-recycle'),
    ).toContainText('ON');

    await page
      .getByTestId('hrro-phase-pf')
      .click();

    await expect(
      page.getByTestId('hrro-phase-status'),
    ).toContainText('PF');

    await expect(
      page.getByTestId('hrro-flow-drain'),
    ).toContainText(
      formattedFlow(drain),
    );

    await expect(
      page.getByTestId('hrro-flow-recycle'),
    ).toContainText(
      formattedFlow(recycle),
    );

    const body = page.locator('body');

    await expect(body).not.toContainText(
      'AquaNova 정밀 모드',
    );
    await expect(body).not.toContainText('APPLIED');
    await expect(body).not.toContainText('SHADOW');
  },
);
