# scripts/dump_screen_text.py
import asyncio
from playwright.async_api import async_playwright
import os


async def dump_screen():
    os.makedirs(".logs", exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=50)
        context = await browser.new_context(viewport={"width": 1600, "height": 900})
        page = await context.new_page()

        print("🌐 1. 페이지 로딩 중...")
        await page.goto("http://127.0.0.1:5173/")
        await page.wait_for_load_state("networkidle")

        print("📦 2. RO 공정 드래그 앤 드롭...")
        palette_item = page.locator("div[draggable='true']:has-text('RO')").first
        canvas = page.locator(".react-flow__pane")
        await palette_item.drag_to(canvas)
        await asyncio.sleep(1)

        print("🔗 3. '자동 연결' 클릭...")
        await page.locator("button:has-text('자동 연결')").first.click(force=True)
        await asyncio.sleep(1)

        print("🖱️ 4. Feed 노드 더블클릭 시도...")
        feed_node = page.locator(".react-flow__node[data-id='feed']")
        if await feed_node.count() == 0:
            feed_node = page.locator(".react-flow__node:has-text('Feed')").first
        await feed_node.dblclick(force=True)

        # 모달이 뜨고 애니메이션이 끝날 때까지 넉넉하게 3초 대기
        await asyncio.sleep(3)

        print("\n==================================================")
        print(" 🔍 [화면 텍스트 추출 결과] 🔍 ")
        print("==================================================")

        # 1. 제목 태그 (보통 모달창 제목)
        headers = await page.evaluate(
            "Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, h6')).map(el => el.innerText.trim()).filter(t => t)"
        )
        print("\n▶ [제목 태그 (h1~h6)]")
        for i, h in enumerate(headers):
            print(f"  {i+1}. '{h}'")

        # 2. 라벨 및 필드 이름들
        labels = await page.evaluate(
            "Array.from(document.querySelectorAll('label, .text-xs.font-bold, .text-\\\\[10px\\\]')).map(el => el.innerText.trim()).filter(t => t)"
        )
        print("\n▶ [라벨 & 작은 제목들]")
        for i, l in enumerate(set(labels)):  # 중복 제거
            print(f"  - '{l}'")

        # 3. 버튼 텍스트
        buttons = await page.evaluate(
            "Array.from(document.querySelectorAll('button')).map(el => el.innerText.trim()).filter(t => t)"
        )
        print("\n▶ [버튼 텍스트]")
        for i, b in enumerate(set(buttons)):
            print(f"  - '{b}'")

        print("\n==================================================")

        # 실제 눈으로 볼 수 있게 스크린샷도 하나 찍어둡니다.
        await page.screenshot(path=".logs/debug_modal_status.png")
        print("\n📸 현재 화면이 '.logs/debug_modal_status.png' 에 저장되었습니다.")
        print("   -> 모달이 정상적으로 열렸는지 사진으로도 꼭 확인해 주세요!")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(dump_screen())
