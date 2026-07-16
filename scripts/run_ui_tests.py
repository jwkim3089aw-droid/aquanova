# scripts/run_ui_tests.py
import asyncio
import json
import logging
import re
import time
import os
from playwright.async_api import async_playwright

DB_PATH = "./.data/wave_extracted_dataset.json"
RESULT_FILE = ".logs/test_results.csv"

logger = logging.getLogger("AquaNovaQA")
logger.setLevel(logging.INFO)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s"
)


def get_unit_type(model_name: str) -> str:
    upper_name = model_name.upper()
    if "SOAR" in upper_name or "CCRO" in upper_name:
        return "HRRO"
    if "NF" in upper_name:
        return "NF"
    if "SFP" in upper_name or "INTEGRAFLUX" in upper_name:
        return "UF"
    return "RO"


def calculate_error(sim: float, target: float) -> str:
    if target == 0:
        return "N/A"
    err = abs(sim - target) / target * 100
    return "PASS" if err <= 15.0 else f"FAIL ({err:.1f}%)"


async def safe_fill_input(page, label_text, value):
    if value is None:
        value = 100.0
    selector = (
        f"xpath=//div[contains(text(), '{label_text}')]//following-sibling::input"
    )
    locator = page.locator(selector).first
    await locator.wait_for(state="visible", timeout=5000)
    await locator.fill("")
    await page.wait_for_timeout(500)
    await locator.fill(str(value))
    await locator.dispatch_event("input")
    await locator.dispatch_event("change")


async def run_final_qa():
    os.makedirs(".logs", exist_ok=True)
    with open(DB_PATH, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=50)
        context = await browser.new_context(viewport={"width": 1600, "height": 900})
        page = await context.new_page()

        with open(RESULT_FILE, "w", encoding="utf-8") as f:
            f.write("model,sim_pressure,sim_tds,status_p,status_t\n")

        for idx, record in enumerate(dataset):
            model_name = record.get("membrane_model", "Unknown").strip()
            unit_type = get_unit_type(model_name)
            logger.info(f"\n[TEST {idx+1}] Model: {model_name} (Type: {unit_type})")

            try:
                # 0. 초기화
                await page.goto("http://127.0.0.1:5173/", timeout=60000)
                await page.wait_for_load_state("networkidle")

                # ✨ [패치 1] 화면을 덮고 있는 모달/팝업창 강제 종료
                # 1) ESC 키를 눌러서 닫을 수 있는 팝업 닫기
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(300)
                await page.keyboard.press("Escape")  # 혹시 몰라 두 번 입력
                await page.wait_for_timeout(500)

                # 2) 만약 반드시 버튼을 눌러야 닫히는 웰컴/새 프로젝트 모달이라면 클릭해서 닫기
                modal_close_btn = page.locator(
                    "button:has-text('닫기'), button:has-text('새 시나리오'), button:has-text('시작')"
                ).first
                if await modal_close_btn.is_visible(timeout=1000):
                    await modal_close_btn.click(force=True)
                await page.wait_for_timeout(500)

                # 1. 공정 드래그 앤 드롭 (겹치지 않게 타겟 위치를 x=500, y=300 으로 지정!)
                palette_item = page.locator(
                    f"div[draggable='true']:has-text('{unit_type}')"
                ).first
                canvas = page.locator(".react-flow__pane")
                await palette_item.drag_to(canvas, target_position={"x": 500, "y": 300})
                await page.wait_for_timeout(1000)

                # 2. '자동 연결' 클릭
                # ✨ [패치 2] 투명한 가림막이 남아있더라도 무시하고 강제 클릭(force=True)
                await page.locator("button:has-text('자동 연결')").first.click(
                    force=True
                )
                await page.wait_for_timeout(1000)

                # 3. Feed 수질 설정
                feed_node = page.locator(".react-flow__node[data-id='feed']")
                if await feed_node.count() == 0:
                    feed_node = page.locator(".react-flow__node:has-text('Feed')").first

                # force=True 제거 (다른 것에 가려져있으면 봇이 알아차릴 수 있게)
                await feed_node.dblclick()

                # Feed 모달 로딩 대기
                await page.wait_for_selector(
                    "text=수질 분석", state="visible", timeout=5000
                )

                # 유입 유량 입력
                await safe_fill_input(page, "유입 유량", record.get("feed_flow"))

                # TDS 입력
                tds_val = record.get("feed_tds")
                if tds_val is None:
                    tds_val = 300.0
                tds_input = page.locator("input[placeholder='NaCl mg/L']").first
                await tds_input.wait_for(state="visible")
                await tds_input.fill("")
                await page.wait_for_timeout(500)
                await tds_input.fill(str(tds_val))
                await tds_input.dispatch_event("input")
                await tds_input.dispatch_event("change")

                # 모달 하단 전체 적용 버튼
                await page.locator("button.bg-blue-600:has-text('적용')").first.click()
                await page.wait_for_timeout(1000)

                # 4. 멤브레인 모델 선택
                unit_node = page.locator(
                    ".react-flow__node:not([data-id='feed']):not([data-id='product'])"
                ).first
                await unit_node.dblclick()

                # 멤브레인 모달 로딩 대기
                await page.wait_for_selector(
                    "text=멤브레인 규격", state="visible", timeout=5000
                )

                await page.evaluate(f"""() => {{
                    const selects = Array.from(document.querySelectorAll('select'));
                    const vendorSelect = selects.find(s => s.innerText.includes('제조사'));
                    if(vendorSelect) {{
                        const option = Array.from(vendorSelect.options).find(opt => opt.text.toUpperCase().includes('{model_name.upper()}'));
                        if (option) {{
                            vendorSelect.value = option.value;
                            vendorSelect.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        }}
                    }}
                }}""")
                await page.wait_for_timeout(1000)
                await page.locator("button.bg-blue-600:has-text('적용')").first.click()
                await page.wait_for_timeout(1000)

                # 5. 시뮬레이션 실행
                await page.locator("button:has-text('실행')").first.click()
                logger.info("  - 🚀 시뮬레이션 실행 중...")
                await page.wait_for_timeout(8000)

                # 6. 결과 추출
                full_text = await page.locator("body").inner_text()

                press_m = re.search(r"유입\s*압력[^\d]*([\d\.]+)", full_text)
                tds_m = re.search(r"생산수\s*TDS[^\d]*([\d\.]+)", full_text)

                sim_p = float(press_m.group(1)) if press_m else 0.0
                sim_t = float(tds_m.group(1)) if tds_m else 0.0

                res_p = calculate_error(sim_p, record.get("feed_pressure", 0))
                res_t = calculate_error(sim_t, record.get("permeate_tds", 0))

                logger.info(f"  [결과] NDP: {sim_p:.2f} bar | TDS: {sim_t:.2f} mg/L")
                logger.info(f"  [판정] {res_p} | {res_t}")

                with open(RESULT_FILE, "a", encoding="utf-8") as f:
                    f.write(f"{model_name},{sim_p},{sim_t},{res_p},{res_t}\n")

            except Exception as e:
                logger.error(f"  - ❌ 테스트 실패: {e}")

        await browser.close()
        logger.info(f"\n🎉 모든 작업 완료. 결과는 {RESULT_FILE}에서 확인 가능합니다.")


if __name__ == "__main__":
    asyncio.run(run_final_qa())
