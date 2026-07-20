import { expect, test, type Page, type Route } from '@playwright/test';

const SESSION_KEY = 'AQUANOVA_SESSION_V1';

function sessionState(membraneModel?: string) {
  return {
    unitMode: 'SI',
    scenarioName: 'V134 NF automatic model',
    nodes: [
      {
        id: 'feed',
        type: 'endpoint',
        position: { x: 40, y: 160 },
        data: { type: 'endpoint', role: 'feed', label: 'Feed' },
      },
      {
        id: 'nf-stage-1',
        type: 'unit',
        position: { x: 420, y: 160 },
        data: {
          type: 'unit',
          kind: 'NF',
          label: 'NF Stage',
          cfg: {
            module_type: 'NF',
            membrane_mode: 'catalog',
            ...(membraneModel ? { membrane_model: membraneModel } : {}),
            mode: 'recovery',
            pressure_bar: 10,
            recovery_target_pct: 75,
            num_stages: 1,
            element_inch: 8,
            vessel_count: 10,
            elements_per_vessel: 5,
            elements: 50,
            membrane_area_m2: 37.2,
            flow_factor: 0.85,
            permeate_back_pressure_bar: 0,
            stages: [
              {
                stage_idx: 1,
                vessel_count: 10,
                elements_per_vessel: 5,
                elements: 50,
                flow_factor: 0.85,
                spi: 0,
                pre_stage_dp_bar: 0,
                isbp_pressure_bar: 0,
                isbp_eff_pct: 0,
              },
            ],
          },
        },
      },
      {
        id: 'product',
        type: 'endpoint',
        position: { x: 900, y: 160 },
        data: { type: 'endpoint', role: 'product', label: 'Product' },
      },
    ],
    edges: [
      { id: 'feed-to-nf', source: 'feed', target: 'nf-stage-1' },
      { id: 'nf-to-product', source: 'nf-stage-1', target: 'product' },
    ],
  };
}

function apiResult(options: { productTds: number; shadow?: boolean }) {
  return {
    scenario_id: 'v134-nf-ui-e2e',
    streams: [
      {
        label: 'Feed',
        flow_m3h: 100,
        tds_mgL: 1000,
        ph: 7,
        pressure_bar: 0,
      },
      {
        label: 'Product',
        flow_m3h: 75,
        tds_mgL: options.productTds,
        ph: 7,
        pressure_bar: 0,
      },
      {
        label: 'Brine',
        flow_m3h: 25,
        tds_mgL: 3460,
        ph: 7,
        pressure_bar: 0,
      },
    ],
    kpi: {
      recovery_pct: 75,
      flux_lmh: 18,
      ndp_bar: 6.2,
      sec_kwhm3: 0.16,
      prod_tds: options.productTds,
      mass_balance: {
        flow_error_m3h: 0,
        flow_error_pct: 0,
        salt_error_kgh: 0,
        salt_error_pct: 0,
        is_balanced: true,
      },
    },
    stage_metrics: [
      {
        stage: 1,
        module_type: 'NF',
        recovery_pct: 75,
        flux_lmh: 18,
        sec_kwhm3: 0.16,
        ndp_bar: 6.2,
        p_in_bar: 12.5,
        p_out_bar: 9.5,
        dp_bar: 0.5,
        Qf: 100,
        Qp: 75,
        Qc: 25,
        Cf: 1000,
        Cp: options.productTds,
        Cc: 3460,
      },
    ],
    warnings: [],
    chemistry: { feed: {}, final_brine: {} },
    precision_report: {
      schema_version: 'aquanova.precision_report.v123',
      enabled: true,
      mode: 'precision',
      status: 'corrected',
      applied_count: options.shadow ? 2 : 3,
      skipped_count: options.shadow ? 1 : 0,
      process_type: 'nf',
      scope: 'nf_standard',
      corrections: [
        {
          metric: 'feed_pressure',
          status: 'applied',
          raw_value: 10,
          corrected_value: 12.5,
        },
        {
          metric: 'specific_energy',
          status: 'applied',
          raw_value: 0.12,
          corrected_value: 0.16,
        },
        {
          metric: 'product_tds',
          status: options.shadow ? 'shadow_only' : 'applied',
          raw_value: options.productTds,
          corrected_value: options.productTds,
        },
      ],
    },
  };
}

async function prepareScenario(
  page: Page,
  membraneModel: string | undefined,
  result: ReturnType<typeof apiResult>,
) {
  await page.addInitScript(
    ({ key, state }) => {
      window.sessionStorage.setItem(key, JSON.stringify(state));
      window.localStorage.clear();
    },
    { key: SESSION_KEY, state: sessionState(membraneModel) },
  );

  await page.route('**/api/v1/simulation/run', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(result),
    });
  });

  await page.goto('/');
}

test('original workspace exposes no model internals', async ({
  page,
}) => {
  await page.goto('/');

  await expect(
    page.getByRole('button', { name: '실행', exact: true }),
  ).toBeVisible();

  await expect(page.getByText('AquaNova 정밀 모드')).toHaveCount(0);
  await expect(page.getByText('OFF · 기본')).toHaveCount(0);
  await expect(page.getByText('ON · 정밀')).toHaveCount(0);
  await expect(page.getByText('APPLIED')).toHaveCount(0);
  await expect(page.getByText('SHADOW')).toHaveCount(0);
});

test('NF270 automatically requests the validated calculation path', async ({
  page,
}) => {
  await prepareScenario(
    page,
    'filmtec-nf270-400-34',
    apiResult({ productTds: 180 }),
  );

  const requestPromise = page.waitForRequest('**/api/v1/simulation/run');
  await page.getByRole('button', { name: '실행', exact: true }).click();

  const payload = (await requestPromise).postDataJSON();
  expect(payload.precision_mode_enabled).toBe(true);
  expect(payload.engine_mode).toBe('precision');
  expect(payload.stages[0].membrane_model).toBe('filmtec-nf270-400-34');

  const resultPanel = page.locator('body');
  await expect(resultPanel).toContainText('생산수 (TDS)');
  await expect(resultPanel).toContainText('180');
  await expect(resultPanel).not.toContainText('정밀 모드');
  await expect(resultPanel).not.toContainText('APPLIED');
});

test('NF90 keeps the public TDS result without exposing shadow status', async ({
  page,
}) => {
  await prepareScenario(
    page,
    'filmtec-nf90-400-34',
    apiResult({ productTds: 35, shadow: true }),
  );

  const requestPromise = page.waitForRequest('**/api/v1/simulation/run');
  await page.getByRole('button', { name: '실행', exact: true }).click();

  const payload = (await requestPromise).postDataJSON();
  expect(payload.precision_mode_enabled).toBe(true);
  expect(payload.stages[0].membrane_model).toBe('filmtec-nf90-400-34');

  const resultPanel = page.locator('body');
  await expect(resultPanel).toContainText('35');
  await expect(resultPanel).not.toContainText('SHADOW');
  await expect(resultPanel).not.toContainText('공개값 유지');
});
