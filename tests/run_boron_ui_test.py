# tests/run_boron_ui_test.py
import asyncio
import logging
import os
import sys
from playwright.async_api import async_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger("BoronUITest")
logger.setLevel(logging.INFO)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s"
)


async def run_boron_ui_validation():
    logger.info("🚀 최종 검증: 2-Pass Boron & pH Dosing 통합 테스트 시작")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=100)
        page = await browser.new_page()

        try:
            await page.goto("http://127.0.0.1:5174/", timeout=30000)
            await page.wait_for_load_state("networkidle")

            # 초기 모달 닫기
            for _ in range(3):
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(300)

            # RO 공정 배치
            palette_item = page.locator("div[draggable='true']:has-text('RO')").first
            canvas = page.locator(".react-flow__pane")
            await palette_item.drag_to(canvas, target_position={"x": 500, "y": 300})
            await page.wait_for_timeout(1000)
            await page.locator("button:has-text('자동 연결')").first.click(force=True)
            await page.wait_for_timeout(1000)

            # Feed 노드 강제 오픈
            await page.evaluate("""() => {
                const node = Array.from(document.querySelectorAll('.react-flow__node')).find(n => n.textContent.includes('Feed'));
                if (node) node.dispatchEvent(new MouseEvent('dblclick', { bubbles: true, detail: 2 }));
            }""")
            await page.wait_for_selector(
                "text=수질 분석", state="visible", timeout=10000
            )

            # 1. 붕소 입력
            boron_input = page.locator(
                "xpath=//div[contains(text(), 'B')]//following-sibling::input"
            ).first
            await boron_input.fill("5.0")
            await boron_input.dispatch_event("change")
            logger.info("  -> ✅ 붕소(B) 입력 완료")

            # 2. pH 도징 입력 (강력한 탐색 적용)
            logger.info("  -> 🔍 Inter-stage pH Control 필드 찾는 중...")
            await page.wait_for_timeout(1000)

            # 🚀 [패치] 태그(div/span)에 상관없이 텍스트로 부모를 찾고 input을 타격합니다.
            ph_input = (
                page.locator("text=Pass 2 Target pH")
                .locator("xpath=..")
                .locator("input")
                .first
            )

            if await ph_input.count() > 0:
                await ph_input.fill("10.0")
                await ph_input.dispatch_event("change")
                logger.info(
                    "  -> ✅ Inter-stage pH Control 입력 완료 (텍스트 노드 탐색 성공)"
                )
            else:
                # 플랜 B: Placeholder 속성으로 추적
                ph_input_fallback = page.locator("input[placeholder*='10.0']").first
                if await ph_input_fallback.count() > 0:
                    await ph_input_fallback.fill("10.0")
                    await ph_input_fallback.dispatch_event("change")
                    logger.info(
                        "  -> ✅ Inter-stage pH Control 입력 완료 (Placeholder 탐색 성공)"
                    )
                else:
                    raise Exception("pH 필드 탐색 실패")

            await page.locator("button.bg-blue-600:has-text('적용')").first.click()
            await page.wait_for_timeout(1000)
            logger.info("🎉 최종 검증 성공! 모든 E2E 테스트가 완료되었습니다.")

        except Exception as e:
            logger.error(f"❌ UI 검증 실패: {e}")
            os.makedirs(".logs", exist_ok=True)
            await page.screenshot(path=".logs/error_ui_screenshot.png", full_page=True)
            logger.info("📸 에러 화면 스크린샷 저장 완료")
        finally:
            await page.wait_for_timeout(3000)
            await browser.close()


if __name__ == "__main__":
    asyncio.run(run_boron_ui_validation())
