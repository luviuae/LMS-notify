from __future__ import annotations

import os
import time
from datetime import datetime

from lms_time import now_lms, parse_lms_due_datetime
from pathlib import Path
from dataclasses import asdict, dataclass
from typing import Iterable

from dotenv import load_dotenv
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Browser, BrowserContext, FrameLocator, Page, sync_playwright
from typing import Any  # 파일 상단에 Any 임포트가 없다면 추가해주세요

LOGIN_URL = "https://lms.ssu.ac.kr/"
DASHBOARD_URL = "https://lms.ssu.ac.kr/mypage"
SMARTID_HOST_KEYWORD = "smartid.ssu.ac.kr"
SSO_COMPLETE_TIMEOUT_MS = 45000
FAIL_PAUSE_MS = 8000
DEFAULT_TIMEOUT_MS = 60000  # iframe 로드 지연 대비 30초 → 60초
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

DEBUG_DIRNAME = "ssu_lms_debug"
DEBUG_ENV_KEY = "SSU_DEBUG"
DASHBOARD_IFRAME_SELECTOR = "#fulliframe"
EXPAND_ALL_BUTTON = "button.xnms-all-fold-btn:has-text('모두 펼치기')"
TODO_ITEM_SELECTOR = (
    ".xn-student-todo-item-container:has(.xnsti-left-icon.assignment), "
    ".xn-student-todo-item-container:has(.xnsti-left-icon.video)"
)
PAST_DUE_KEYWORD = "기한지남"


def debug_enabled() -> bool:
    return os.getenv(DEBUG_ENV_KEY, "false").lower() == "true"


def debug_capture(page: Page, stage: str) -> None:
    """
    Save a screenshot + a small url log to help diagnose where flow breaks.
    Keep it opt-in via SSU_DEBUG to avoid generating artifacts unnecessarily.
    """
    if not debug_enabled():
        return

    out_dir = Path(__file__).resolve().parent / DEBUG_DIRNAME
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = int(time.time() * 1000)
    safe_stage = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in stage)
    (out_dir / f"{safe_stage}_{ts}.url.txt").write_text(
        f"stage={stage}\nurl={page.url}\n", encoding="utf-8"
    )
    # Screenshot may contain personal info; only enable when you accept local debug artifacts.
    page.screenshot(path=str(out_dir / f"{safe_stage}_{ts}.png"), full_page=True)


@dataclass
class Assignment:
    course_name: str
    title: str
    due_date: str
    detail_link: str


def first_visible(page: Page, selectors: Iterable[str]):
    for selector in selectors:
        locator = page.locator(selector).first
        if locator.count() > 0 and locator.is_visible():
            return locator
    return None


def on_smartid_login_page(url: str) -> bool:
    return SMARTID_HOST_KEYWORD in url and "smln.asp" in url


def is_lms_session_active(page: Page) -> bool:
    url = page.url
    if "lms.ssu.ac.kr" not in url or SMARTID_HOST_KEYWORD in url:
        return False
    if on_smartid_login_page(url):
        return False
    if first_visible(
        page,
        [
            "text=통합 로그인",
            "a:has-text('통합 로그인')",
            "button:has-text('통합 로그인')",
        ],
    ):
        return False
    return True


def wait_for_sso_completion(page: Page, timeout_ms: int) -> bool:
    """
    SmartID posts credentials to a hidden iframe (pFrame), then redirects the parent.
    The parent URL stays on smln.asp until that finishes — do not treat that as failure.
    """
    deadline = time.time() + (timeout_ms / 1000)
    pframe_seen = False

    while time.time() < deadline:
        url = page.url
        if "lms.ssu.ac.kr" in url and SMARTID_HOST_KEYWORD not in url:
            return True

        frame = page.frame(name="pFrame")
        if frame is not None:
            pframe_seen = True
            try:
                frame_url = frame.url
                if frame_url and "smln_pcs.asp" in frame_url:
                    # iframe finished credential check; parent redirect usually follows
                    page.wait_for_timeout(800)
            except PlaywrightError:
                pass

        if pframe_seen and not on_smartid_login_page(url):
            return True

        page.wait_for_timeout(400)

    return False


def pause_before_browser_close(headless: bool) -> None:
    if headless:
        return
    keep_open = os.getenv("SSU_KEEP_BROWSER_OPEN", "true").lower() == "true"
    if not keep_open:
        return
    pause_ms = int(os.getenv("SSU_FAIL_PAUSE_MS", str(FAIL_PAUSE_MS)))
    print(
        f"[안내] 브라우저를 {pause_ms / 1000:.0f}초간 유지합니다. "
        "(로그인 화면 확인용 — SSU_KEEP_BROWSER_OPEN=false 로 끌 수 있음)"
    )
    time.sleep(pause_ms / 1000)


def login_lms(
    page: Page,
    username: str,
    password: str,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> bool:
    try:
        page.goto(LOGIN_URL, wait_until="domcontentloaded")
    except PlaywrightError as exc:
        print(f"[접속 실패] 로그인 페이지 이동 중 오류가 발생했습니다: {exc}")
        return False

    debug_capture(page, "01_lms_home_loaded")
    print(f"[로그인 흐름] 시작 URL: {page.url}")

    # Start from LMS home and enter SSO login flow.
    sso_entry = first_visible(
        page,
        [
            "button:has-text('통합 로그인')",
            "a:has-text('통합 로그인')",
            "text=통합 로그인",
        ],
    )
    if not sso_entry:
        print(f"[로그인 실패] '통합 로그인' 버튼을 찾지 못했습니다. 현재 URL: {page.url}")
        return False

    sso_entry.click()
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(700)
    debug_capture(page, "02_after_click_sso")

    if SMARTID_HOST_KEYWORD not in page.url:
        # Some pages open the SSO flow with an extra redirect delay.
        page.wait_for_timeout(1500)
    debug_capture(page, "03_sso_redirected")

    on_smartid = SMARTID_HOST_KEYWORD in page.url
    id_locator = first_visible(
        page,
        (
            ["#userid", "input[name='userid']", "input#userid"]
            if on_smartid
            else []
        )
        + [
            "#login_user_id",
            "#user_id",
            "#id",
            "input[name='login_user_id']",
            "input[name='user_id']",
            "input[name='id']",
            "input[name='userid']",
            "input[name='username']",
            "input[placeholder*='아이디']",
            "input[type='text']",
        ],
    )
    pw_locator = first_visible(
        page,
        (
            ["#pwd", "input[name='pwd']", "input#pwd"]
            if on_smartid
            else []
        )
        + [
            "#login_user_password",
            "#password",
            "#pw",
            "input[name='login_user_password']",
            "input[name='password']",
            "input[name='pw']",
            "input[name='passwd']",
            "input[placeholder*='비밀번호']",
            "input[type='password']",
        ],
    )

    if not id_locator or not pw_locator:
        print(f"[로그인 실패] 아이디/비밀번호 입력 폼을 찾지 못했습니다. 현재 URL: {page.url}")
        return False

    id_locator.click()
    id_locator.fill(username)
    pw_locator.click()
    pw_locator.fill(password)

    # SmartID uses JavaScript LoginInfoSend + hidden iframe; Enter/submit often do nothing in Chromium.
    login_btn = first_visible(
        page,
        [
            "a.btn_login",
            "a:has-text('로그인')",
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('로그인')",
        ],
    )
    if not login_btn:
        print(f"[로그인 실패] 로그인 버튼을 찾지 못했습니다. 현재 URL: {page.url}")
        return False

    login_btn.click()

    sso_timeout = int(os.getenv("SSU_SSO_TIMEOUT_MS", str(SSO_COMPLETE_TIMEOUT_MS)))
    if on_smartid_login_page(page.url):
        print(f"[로그인 흐름] SSO iframe 처리 대기 중 (최대 {sso_timeout / 1000:.0f}초)...")
        if not wait_for_sso_completion(page, timeout_ms=sso_timeout):
            debug_capture(page, "04_sso_timeout")
            print(
                "[로그인 실패] SSO 완료 대기 시간을 초과했습니다. "
                "아이디/비밀번호, 2차 인증, 또는 네트워크를 확인해주세요."
            )
            print(f"[로그인 흐름] 현재 URL: {page.url}")
            return False

    try:
        page.wait_for_load_state("domcontentloaded", timeout=10000)
    except PlaywrightTimeoutError:
        page.wait_for_timeout(1000)

    debug_capture(page, "04_after_submit")
    print(f"[로그인 흐름] 제출 후 URL: {page.url}")

    auth_fail_banner = first_visible(
        page,
        [
            "text=사용자 인증에 실패",
            "text=인증에 실패",
            "text=로그인 실패",
            "text=일치하지",
            "text=잘못",
        ],
    )
    if auth_fail_banner:
        print("[로그인 실패] 사용자 인증에 실패했습니다. 아이디/비밀번호 또는 인증 정책을 확인해주세요.")
        debug_capture(page, "05_auth_fail_banner")
        return False

    if on_smartid_login_page(page.url):
        print(
            "[로그인 실패] SSO 로그인 페이지에 머물러 있습니다. "
            "자격 증명 또는 추가 인증(캡차/팝업)이 필요할 수 있습니다."
        )
        debug_capture(page, "06_still_on_smartid")
        return False

    if not is_lms_session_active(page):
        print(f"[로그인 실패] LMS 세션이 활성화되지 않았습니다. 현재 URL: {page.url}")
        debug_capture(page, "06_lms_session_inactive")
        return False

    print("[로그인 성공] LMS 세션 확인됨. 마이페이지로 이동합니다.")
    try:
        page.goto(DASHBOARD_URL, wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle", timeout=20000)
    except PlaywrightTimeoutError:
        page.wait_for_timeout(2000)
    except PlaywrightError as exc:
        print(f"[로그인 실패] 마이페이지 이동 중 오류가 발생했습니다: {exc}")
        debug_capture(page, "08_nav_mypage_error")
        return False

    debug_capture(page, "08_goto_mypage")
    print(f"[로그인 흐름] 마이페이지 URL: {page.url}")

    if not is_lms_session_active(page):
        print("[로그인 실패] 마이페이지 이동 후 세션이 유지되지 않았습니다.")
        debug_capture(page, "09_mypage_session_lost")
        return False

    debug_capture(page, "09_mypage_ready")
    return True


def get_dashboard_frame(page: Page, timeout_ms: int) -> FrameLocator:
    """마이페이지 본문은 canvas.ssu.ac.kr 대시보드 iframe에 렌더링됩니다."""
    try:
        page.wait_for_selector(DASHBOARD_IFRAME_SELECTOR, state="attached", timeout=timeout_ms)
    except PlaywrightTimeoutError:
        print(f"[디버그] iframe 선택자({DASHBOARD_IFRAME_SELECTOR})를 찾지 못함. 현재 URL: {page.url}")
        raise

    # iframe 로드 후 추가 대기 (네트워크가 느린 경우 대비)
    page.wait_for_timeout(1000)

    frame = page.frame_locator(DASHBOARD_IFRAME_SELECTOR)
    try:
        frame.locator(".xn-dash-board, .xnms-my-subject-title").first.wait_for(
            state="visible",
            timeout=timeout_ms,
        )
    except PlaywrightTimeoutError:
        print(f"[디버그] iframe 내부 대시보드 콘텐츠를 찾지 못함. iframe 존재 여부 확인 중...")
        if page.locator(DASHBOARD_IFRAME_SELECTOR).count() > 0:
            print(f"[디버그] iframe은 존재하지만 내부 콘텐츠가 미로드 상태")
        else:
            print(f"[디버그] iframe 자체가 DOM에 없음")
        raise
    return frame


#def expand_all_todo_sections(frame: FrameLocator, timeout_ms: int) -> bool:
#    expand_btn = frame.locator(EXPAND_ALL_BUTTON).first
#    if expand_btn.count() == 0:
#        expand_btn = frame.get_by_role("button", name="모두 펼치기").first
#    if expand_btn.count() == 0:
#        print("[알림] '모두 펼치기' 버튼을 찾지 못했습니다.")
#        return False
#
#    expand_btn.click()
#    try:
#        frame.locator(TODO_ITEM_SELECTOR).first.wait_for(
#            state="attached", timeout=timeout_ms
#        )
#    except PlaywrightTimeoutError:
#        pass
#    return True

def expand_all_todo_sections(frame: FrameLocator, timeout_ms: int) -> bool:
    # 1. '모두 펼치기' 버튼이 화면에 완전히 나타나고 글자가 보일 때까지 명시적으로 대기합니다.
    # 여러 셀렉터 후보를 콤마(,)로 연결하여 하나라도 일치하면 대기하도록 설정합니다.
    target_locator = frame.locator(f"{EXPAND_ALL_BUTTON}, button:has-text('모두 펼치기')").first
    
    try:
        print("[디버그] '모두 펼치기' 버튼이 렌더링되기를 기다리는 중...")
        target_locator.wait_for(state="visible", timeout=timeout_ms)
    except PlaywrightTimeoutError:
        print("[알림] '모두 펼치기' 버튼이 지정된 시간 내에 화면에 표시되지 않았습니다.")
        return False

    # 2. 버튼 클릭 및 이후 할 일 목록 대기
    try:
        target_locator.click()
        print("[디버그] '모두 펼치기' 버튼을 클릭했습니다. 할 일 목록 로딩 대기 중...")
        
        frame.locator(TODO_ITEM_SELECTOR).first.wait_for(
            state="attached", timeout=timeout_ms
        )
        return True
    except PlaywrightError as e:
        print(f"[알림] 버튼 클릭 또는 할 일 목록 로드 중 오류 발생: {e}")
        return False


def is_active_assignment(dday_text: str, due_date: str) -> bool:
    text = dday_text.strip()
    if PAST_DUE_KEYWORD in text:
        return False
    if text.startswith("D-"):
        return True
    due_dt = parse_lms_due_datetime(due_date)
    if due_dt is not None:
        return due_dt >= now_lms()
    try:
        due_dt = datetime.strptime(due_date.strip(), "%Y.%m.%d %H:%M")
        return due_dt >= datetime.now()
    except ValueError:
        return PAST_DUE_KEYWORD not in text


def collect_assignments(page: Page, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> list[Assignment]:
    if "mypage" not in page.url:
        try:
            page.goto(DASHBOARD_URL, wait_until="domcontentloaded")
        except PlaywrightError as exc:
            print(f"[알림] 마이페이지 이동 실패: {exc}")
            return []

    max_retries = 2
    for attempt in range(max_retries):
        try:
            frame = get_dashboard_frame(page, timeout_ms=timeout_ms)
            break
        except PlaywrightTimeoutError:
            if attempt < max_retries - 1:
                print(f"[알림] iframe 로드 실패 (시도 {attempt + 1}/{max_retries}). 2초 대기 후 재시도...")
                page.wait_for_timeout(2000)
                try:
                    page.reload(wait_until="domcontentloaded")
                except PlaywrightError:
                    pass
            else:
                print("[알림] 마이페이지 대시보드 iframe을 불러오지 못했습니다.")
                return []

    if not expand_all_todo_sections(frame, timeout_ms=timeout_ms):
        return []

    only_active = os.getenv("SSU_ONLY_ACTIVE_ASSIGNMENTS", "true").lower() == "true"
    assignments: list[Assignment] = []
    courses = frame.locator(".xn-student-course-container")

    for i in range(courses.count()):
        course = courses.nth(i)
        title_loc = course.locator(".xnscc-header-title").first
        course_name = (
            title_loc.inner_text(timeout=2000).strip()
            if title_loc.count() > 0
            else "과목명 미확인"
        )

        items = course.locator(TODO_ITEM_SELECTOR)
        for j in range(items.count()):
            item = items.nth(j)
            link_loc = item.locator("a.xnsti-left-title").first
            if link_loc.count() == 0:
                continue

            title = link_loc.inner_text(timeout=2000).strip()
            href = link_loc.get_attribute("href") or ""
            due_loc = item.locator(".xnsti-right-due-at").first
            due_date = (
                due_loc.inner_text(timeout=2000).strip()
                if due_loc.count() > 0
                else "마감기한 미확인"
            )
            dday_loc = item.locator(".xnsti-right-dday-text").first
            dday = dday_loc.inner_text(timeout=2000).strip() if dday_loc.count() > 0 else ""

            if only_active and not is_active_assignment(dday, due_date):
                continue

            assignments.append(
                Assignment(
                    course_name=course_name,
                    title=title,
                    due_date=due_date,
                    detail_link=href or "상세 링크 미확인",
                )
            )

    if not assignments:
        print("[알림] iframe 대시보드에서 진행 중인 과제를 찾지 못했습니다.")
    else:
        print(f"[수집 완료] 과제 {len(assignments)}개를 수집했습니다.")
    return assignments


def create_context(
    browser: Browser,
    user_agent: str = DEFAULT_USER_AGENT,
) -> BrowserContext:
    viewport_width = int(os.getenv("SSU_VIEWPORT_WIDTH", "1280"))
    viewport_height = int(os.getenv("SSU_VIEWPORT_HEIGHT", "720"))
    return browser.new_context(
        user_agent=user_agent,
        locale="ko-KR",
        viewport={"width": viewport_width, "height": viewport_height},
    )


def run(
    headless: bool = False,
    user_agent: str = DEFAULT_USER_AGENT,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> list[Assignment]:
    load_dotenv()
    username = os.getenv("SSU_ID")
    password = os.getenv("SSU_PASSWORD")

    if not username or not password:
        raise ValueError(".env 파일에 SSU_ID / SSU_PASSWORD 값을 설정해주세요.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = create_context(browser=browser, user_agent=user_agent)
        page = context.new_page()
        page.set_default_timeout(timeout_ms)

        if not login_lms(page, username, password, timeout_ms=timeout_ms):
            pause_before_browser_close(headless=headless)
            context.close()
            browser.close()
            return []

        assignments = collect_assignments(page, timeout_ms=timeout_ms)
        context.close()
        browser.close()
        return assignments


def print_assignments(assignments: list[Assignment]) -> None:
    if not assignments:
        print("진행 중인 과제를 찾지 못했습니다.")
        return

    print(f"총 {len(assignments)}개의 과제를 찾았습니다.")
    for idx, assignment in enumerate(assignments, start=1):
        payload = asdict(assignment)
        print(f"[{idx}] {payload}")


if __name__ == "__main__":
    headless_flag = os.getenv("SSU_HEADLESS", "false").lower() == "true"
    ua = os.getenv("SSU_USER_AGENT", DEFAULT_USER_AGENT)

    result = run(headless=headless_flag, user_agent=ua)
    print_assignments(result)



def get_dashboard_frame(page: Page, timeout_ms: int) -> Any:
    """마이페이지 본문은 canvas.ssu.ac.kr 대시보드 iframe에 렌더링됩니다.
    이미 Canvas 도메인에 진입했거나 우회 성공한 경우를 포함하여 유연하게 처리합니다.
    """
    # 🌟 [핵심 수정] 이미 Canvas 페이지에 있거나 우회에 성공해 주소가 바뀐 상태라면 
    # 더 이상 iframe을 찾지 않고, 현재 page 자체를 대시보드로 인식하여 즉시 반환합니다.
    if "canvas.ssu.ac.kr" in page.url:
        print(f"[디버그] 현재 이미 Canvas 페이지에 놓여 있습니다. (URL: {page.url})")
        try:
            # 과제 컨테이너 레이아웃 클래스까지 포함하여 유연하게 대기합니다.
            page.wait_for_selector(
                ".xn-dash-board, .xnms-my-subject-title, .xn-student-course-container", 
                state="visible", 
                timeout=timeout_ms
            )
        except PlaywrightTimeoutError:
            print("[디버그] Canvas 대시보드 요소 대기 타임아웃. 일단 수집을 강제 진행합니다.")
        return page

    # lms.ssu.ac.kr 마이페이지인 기본 상태일 때만 iframe 추출을 시작합니다.
    try:
        page.wait_for_selector(DASHBOARD_IFRAME_SELECTOR, state="attached", timeout=timeout_ms)
    except PlaywrightTimeoutError:
        print(f"[디버그] iframe 선택자({DASHBOARD_IFRAME_SELECTOR})를 찾지 못함. 현재 URL: {page.url}")
        raise

    iframe_src = page.locator(DASHBOARD_IFRAME_SELECTOR).first.get_attribute("src")

    # GitHub Actions 환경 우회 로직
    if os.getenv("GITHUB_ACTIONS", "").lower() == "true" and iframe_src:
        print(f"[디버그] GitHub Actions 환경 감지: iframe 제한을 우회하기 위해 Canvas URL로 직접 이동합니다.")
        try:
            # 페이지 로딩 및 세션 유기적 연동을 위해 wait_until을 "load"로 안정화합니다.
            page.goto(iframe_src, wait_until="load", timeout=timeout_ms)
            
            # 대시보드 주소 패턴으로 정상 전환되었는지 URL 검증 대기
            page.wait_for_url("**/learningx/dashboard*", timeout=timeout_ms)
            print(f"[디버그] 직접 이동 완료 (최종 URL: {page.url})")
            
            page.wait_for_selector(
                ".xn-dash-board, .xnms-my-subject-title, .xn-student-course-container", 
                state="visible", 
                timeout=timeout_ms
            )
            return page
        except PlaywrightError as e:
            print(f"[디버그] 직접 이동 처리 중 예외 발생: {e}")
            # 💡 중요: 이동 직후 타임아웃이 났더라도 URL이 이미 canvas로 바뀌었다면 
            # 탈출하지 말고 무조건 page를 반환해서 다음 수집 스텝으로 넘겨줍니다.
            if "canvas.ssu.ac.kr" in page.url:
                print("[디버그] 타임아웃이 발생했으나 URL이 Canvas로 전환되었으므로 page를 반환합니다.")
                return page
            
            print("[디버그] Canvas 전환에 완전히 실패하여 원래 LMS 마이페이지 복귀를 시도합니다.")
            try:
                page.goto(DASHBOARD_URL, wait_until="domcontentloaded")
            except PlaywrightError:
                pass

    # 기존 iframe 방식 진행 (로컬 환경 등 기본 흐름)
    page.wait_for_timeout(1000)
    frame = page.frame_locator(DASHBOARD_IFRAME_SELECTOR)
    try:
        frame.locator(".xn-dash-board, .xnms-my-subject-title, .xn-student-course-container").first.wait_for(
            state="visible",
            timeout=timeout_ms,
        )
        return frame
    except PlaywrightTimeoutError:
        print(f"[디버그] iframe 내부 대시보드 콘텐츠를 찾지 못함. 현재 URL: {page.url}")
        raise

def expand_all_todo_sections(frame: Any, timeout_ms: int) -> bool:
    """'모두 펼치기' 버튼을 누릅니다. race condition 방지를 위해 레이아웃 유연성을 확보합니다."""
    target_locator = frame.locator(f"{EXPAND_ALL_BUTTON}, button:has-text('모두 펼치기')").first
    
    try:
        # 버튼이 화면에 보일 때까지 최대 5초 대기
        target_locator.wait_for(state="visible", timeout=min(5000, timeout_ms))
        target_locator.click()
        print("[디버그] '모두 펼치기' 버튼을 클릭했습니다.")
        
        # 클릭 후 할 일 목록 아이템이 최소 하나 이상 나타날 때까지 대기
        frame.locator(TODO_ITEM_SELECTOR).first.wait_for(
            state="attached", timeout=min(5000, timeout_ms)
        )
        return True
    except PlaywrightTimeoutError:
        # 가끔 과제가 적거나 이미 펼쳐져 있어 버튼이 안 보이는 경우, 에러로 멈추지 않고 계속 진행하도록 유도합니다.
        print("[알림] '모두 펼치기' 버튼을 찾지 못했거나 이미 펼쳐져 있습니다. 수집을 계속 진행합니다.")
        return True