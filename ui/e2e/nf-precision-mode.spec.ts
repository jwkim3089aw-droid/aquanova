import {
  expect,
  test,
  type Page,
  type Route,
} from '@playwright/test';

const SESSION_KEY = 'AQUANOVA_SESSION_V1';

function sessionState(membraneModel: string) {
  return {
    unitMode: 'SI',
    scenarioName: 'V133 NF UI E2E',
    nodes: [
      {
        id: 'feed',
        type: 'endpoint',
        position: { x: 40, y: 160 },
        data: {
          type: 'endpoint',
          role: 'feed',
          label: 'Feed',
        },
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
            membrane_model: membraneModel,
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
        data: {
          type: 'endpoint',
          role: 'product',
          label: 'Product',
        },
      },
    ],
    edges: [
      {
        id: 'feed-to-nf',
        source: 'feed',
        target: 'nf-stage-1',
      },
      {
        id: 'nf-to-product',
        source: 'nf-stage-1',
        target: 'product',
      },
    ],
  };
}

function apiResult(options: {
  precision?: boolean;
  nf90?: boolean;
}) {
  const precision = Boolean(options.precision);
  const nf90 = Boolean(options.nf90);

  return {
    scenario_id: 'v133-nf-ui-e2e',
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
        tds_mgL: nf90 ? 35 : 180,
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
      sec_kwhm3: precision ? 0.16 : 0.12,
      prod_tds: nf90 ? 35 : 180,
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
        sec_kwhm3: precision ? 0.16 : 0.12,
        ndp_bar: 6.2,
        p_in_bar: precision ? 12.5 : 10,
        p_out_bar: 9.5,
        dp_bar: 0.5,
        Qf: 100,
        Qp: 75,
        Qc: 25,
        Cf: 1000,
        Cp: nf90 ? 35 : 180,
        Cc: 3460,
      },
    ],
    warnings: [],
    chemistry: {
      feed: {},
      final_brine: {},
    },
    precision_report: precision
      ? {
          schema_version:
            'aquanova.precision_report.v123',
          enabled: true,
          mode: 'precision',
          status: 'corrected',
          applied_count: nf90 ? 2 : 3,
          skipped_count: nf90 ? 1 : 0,
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
            nf90
              ? {
                  metric: 'product_tds',
                  status: 'shadow_only',
                  raw_value: 35,
                  corrected_value: 35,
                }
              : {
                  metric: 'product_tds',
                  status: 'applied',
                  raw_value: 220,
                  corrected_value: 180,
                },
          ],
        }
      : null,
  };
}

async function preparePage(
  page: Page,
  membraneModel: string,
  result: ReturnType<typeof apiResult>,
) {
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
      state: sessionState(membraneModel),
    },
  );

  await page.route(
    '**/api/v1/simulation/run',
    async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(result),
      });
    },
  );

  await page.goto('/');
}

test('OFF sends raw mode and displays basic result', async ({
  page,
}) => {
  await preparePage(
    page,
    'filmtec-nf270-400-34',
    apiResult({ precision: false }),
  );

  await expect(
    page.getByTestId('precision-mode-state'),
  ).toHaveText('OFF · 기본');

  const requestPromise = page.waitForRequest(
    '**/api/v1/simulation/run',
  );

  await page
    .getByRole('button', { name: '실행', exact: true })
    .click();

  const request = await requestPromise;
  const payload = request.postDataJSON();

  expect(payload.precision_mode_enabled).toBe(false);
  expect(payload.engine_mode).toBe('raw');

  await expect(
    page.getByTestId('precision-report-panel'),
  ).toContainText('기본 계산');
});

test('NF270 ON sends precision mode and shows 3 applied rows', async ({
  page,
}) => {
  await preparePage(
    page,
    'filmtec-nf270-400-34',
    apiResult({ precision: true }),
  );

  await page
    .getByTestId('precision-mode-toggle-button')
    .click();

  await expect(
    page.getByTestId('precision-mode-state'),
  ).toHaveText('ON · 정밀');

  const requestPromise = page.waitForRequest(
    '**/api/v1/simulation/run',
  );

  await page
    .getByRole('button', { name: '실행', exact: true })
    .click();

  const request = await requestPromise;
  const payload = request.postDataJSON();

  expect(payload.precision_mode_enabled).toBe(true);
  expect(payload.engine_mode).toBe('precision');
  expect(payload.stages[0].membrane_model).toBe(
    'filmtec-nf270-400-34',
  );

  await expect(
    page.getByTestId('precision-applied-count'),
  ).toHaveText('3');

  await expect(
    page.getByTestId('precision-shadow-count'),
  ).toHaveText('0');
});

test('NF90 shows product TDS as shadow-only', async ({
  page,
}) => {
  await preparePage(
    page,
    'filmtec-nf90-400-34',
    apiResult({
      precision: true,
      nf90: true,
    }),
  );

  await page
    .getByTestId('precision-mode-toggle-button')
    .click();

  const requestPromise = page.waitForRequest(
    '**/api/v1/simulation/run',
  );

  await page
    .getByRole('button', { name: '실행', exact: true })
    .click();

  const request = await requestPromise;
  const payload = request.postDataJSON();

  expect(payload.stages[0].membrane_model).toBe(
    'filmtec-nf90-400-34',
  );

  await expect(
    page.getByTestId('precision-applied-count'),
  ).toHaveText('2');

  await expect(
    page.getByTestId('precision-shadow-count'),
  ).toHaveText('1');

  await expect(
    page.getByTestId(
      'precision-correction-product_tds',
    ),
  ).toContainText('SHADOW');

  await expect(
    page.getByTestId(
      'precision-correction-product_tds',
    ),
  ).toContainText('공개값 유지');
});
