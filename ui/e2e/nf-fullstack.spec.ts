import {
  expect,
  test,
  type APIResponse,
  type Page,
} from '@playwright/test';

const SESSION_KEY = 'AQUANOVA_SESSION_V1';

interface RunPayload {
  precision_mode_enabled?: boolean;
  engine_mode?: string;
  stages: Array<{
    membrane_model?: string;
  }>;
}

interface PrecisionCorrection {
  metric: string;
  status: string;
  raw_value: number | null;
  corrected_value: number | null;
}

interface PrecisionReport {
  enabled: boolean;
  mode: string;
  status: string;
  applied_count: number;
  skipped_count: number;
  corrections: PrecisionCorrection[];
}

interface SimulationResponse {
  kpi: {
    prod_tds: number;
  };
  precision_report?: PrecisionReport | null;
}

function sessionState(membraneModel?: string) {
  return {
    unitMode: 'SI',
    scenarioName: 'V135 NF fullstack E2E',
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
            ...(membraneModel
              ? { membrane_model: membraneModel }
              : {}),
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
                spi: 1,
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

async function prepareScenario(
  page: Page,
  membraneModel?: string,
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

  await page.goto('/');
}

async function executeRealSimulation(
  page: Page,
): Promise<{
  payload: RunPayload;
  result: SimulationResponse;
  response: APIResponse;
}> {
  const responsePromise = page.waitForResponse(
    (response) =>
      response.url().includes('/api/v1/simulation/run') &&
      response.request().method() === 'POST',
    {
      timeout: 60_000,
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
  const payload =
    response.request().postDataJSON() as RunPayload;

  expect(
    response.ok(),
    `Simulation API failed: ${response.status()} ${responseText}`,
  ).toBe(true);

  const result =
    JSON.parse(responseText) as SimulationResponse;

  await expect(
    page.getByText('생산수 (TDS)').first(),
  ).toBeVisible({
    timeout: 60_000,
  });

  return {
    payload,
    result,
    response,
  };
}

async function expectNoInternalTerminology(page: Page) {
  const body = page.locator('body');

  await expect(body).not.toContainText('AquaNova 정밀 모드');
  await expect(body).not.toContainText('OFF · 기본');
  await expect(body).not.toContainText('ON · 정밀');
  await expect(body).not.toContainText('APPLIED');
  await expect(body).not.toContainText('SHADOW');
  await expect(body).not.toContainText('WAVE 비교');
}

test.describe.configure({
  mode: 'serial',
});

test('NF270 runs through the real API and SimulationEngine', async ({
  page,
}) => {
  await prepareScenario(
    page,
    'filmtec-nf270-400-34',
  );

  const { payload, result } =
    await executeRealSimulation(page);

  expect(payload.precision_mode_enabled).toBe(true);
  expect(payload.engine_mode).toBe('precision');
  expect(payload.stages[0].membrane_model).toBe(
    'filmtec-nf270-400-34',
  );

  const report = result.precision_report;

  expect(report).toBeTruthy();
  expect(report?.enabled).toBe(true);
  expect(report?.mode).toBe('precision');
  const appliedCount = report?.applied_count ?? 0;

  expect(appliedCount).toBeGreaterThan(0);
  expect(report?.status).not.toBe(
    'layer_missing_or_invalid',
  );

  expect(
    report?.corrections.filter(
      (correction) => correction.status === 'applied',
    ),
  ).toHaveLength(appliedCount);

  expect(Number.isFinite(result.kpi.prod_tds)).toBe(true);
  await expectNoInternalTerminology(page);
});

test('NF90 keeps product TDS internal validation hidden', async ({
  page,
}) => {
  await prepareScenario(
    page,
    'filmtec-nf90-400-34',
  );

  const { payload, result } =
    await executeRealSimulation(page);

  expect(payload.precision_mode_enabled).toBe(true);
  expect(payload.engine_mode).toBe('precision');
  expect(payload.stages[0].membrane_model).toBe(
    'filmtec-nf90-400-34',
  );

  const report = result.precision_report;

  expect(report).toBeTruthy();
  expect(report?.enabled).toBe(true);
  expect(report?.applied_count).toBe(2);

  const productTds = report?.corrections.find(
    (correction) => correction.metric === 'product_tds',
  );

  expect(productTds?.status).toBe('shadow_only');
  expect(Number.isFinite(result.kpi.prod_tds)).toBe(true);
  await expectNoInternalTerminology(page);
});

test('missing membrane safely keeps the physical result', async ({
  page,
}) => {
  await prepareScenario(page);

  const { payload, result } =
    await executeRealSimulation(page);

  expect(payload.precision_mode_enabled).toBe(true);
  expect(payload.engine_mode).toBe('precision');
  expect(
    payload.stages[0].membrane_model ?? '',
  ).toBe('');

  const report = result.precision_report;

  expect(report).toBeTruthy();
  expect(report?.enabled).toBe(true);
  expect(report?.applied_count).toBe(0);
  expect(report?.status).not.toBe(
    'layer_missing_or_invalid',
  );
  expect(report?.corrections ?? []).toHaveLength(0);

  expect(Number.isFinite(result.kpi.prod_tds)).toBe(true);
  await expectNoInternalTerminology(page);
});
