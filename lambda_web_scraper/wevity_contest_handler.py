import re
from datetime import datetime, timedelta
from typing import Dict, Any
import pytz

from common_utils import get_recent_notices, save_notices_to_db, send_slack_notification


def parse_date(date_str: str, kst: pytz.timezone) -> datetime:
    """
    날짜 문자열을 파싱하여 datetime 객체로 변환
    """
    try:
        # "D-60" 형식 파싱
        if "D-" in date_str:
            days_match = re.search(r"D-(\d+)", date_str)
            if days_match:
                days = int(days_match.group(1))
                return datetime.now(kst) + timedelta(days=days)

        # 기본값: 현재 시간
        return datetime.now(kst)
    except Exception as e:
        print(f"⚠️ [PARSER] 날짜 파싱 실패: {date_str}, 오류: {e}")
        return datetime.now(kst)


def _setup_browser():
    """브라우저 설정 및 페이지 생성"""
    from playwright.sync_api import sync_playwright

    p = sync_playwright().start()
    browser = p.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-accelerated-2d-canvas",
            "--no-first-run",
            "--no-zygote",
            "--single-process",
            "--disable-gpu",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-web-security",
            "--disable-features=TranslateUI",
            "--disable-extensions",
        ],
    )

    page = browser.new_page()
    page.set_extra_http_headers(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
    )

    return p, browser, page


def _navigate_to_main_page(page, url):
    """메인 페이지로 이동 및 리스트 로딩 대기"""
    page.goto(url, timeout=30000)
    page.wait_for_selector("ul.list", timeout=10000)
    page.wait_for_timeout(2000)


def _get_contest_items(page):
    """공모전 항목들을 가져오기 (최신 10개만)"""
    items = page.query_selector_all("ul.list li:not(.top)")
    items = items[:10]
    print(f"📊 [SCRAPER] 발견된 공모전 수: {len(items)} (최신 10개만 처리)")
    return items


def _extract_title_from_item(item, index):
    """항목에서 제목 추출"""
    title_element = item.query_selector("div.tit a")
    if not title_element:
        print(f"⚠️ [SCRAPER] 공모전 {index+1} 제목 요소를 찾을 수 없음")
        return None

    title = title_element.evaluate("el => el.textContent").strip()
    # SPECIAL, IDEA 라벨 텍스트 제거
    title = re.sub(r"\b(SPECIAL|IDEA)\b", "", title).strip()
    print(f"📰 [SCRAPER] 제목: '{title}'")
    return title, title_element


def _extract_deadline_from_item(item, index):
    """항목에서 마감일 정보 추출"""
    day_element = item.query_selector("div.day")
    if not day_element:
        print(f"⚠️ [SCRAPER] 공모전 {index+1} 마감일 요소를 찾을 수 없음")
        return None

    day_text = day_element.text_content().strip()
    print(f"📅 [SCRAPER] 마감일 정보: '{day_text}'")
    return day_text


def _extract_link_from_item(item, index):
    """항목에서 링크 추출"""
    link_element = item.query_selector("div.tit a")
    if not link_element:
        print(f"⚠️ [SCRAPER] 공모전 {index+1} 링크 요소를 찾을 수 없음")
        return None

    href = link_element.get_attribute("href")
    if href:
        if href.startswith("?"):
            base_url = "https://www.wevity.com/"
            full_link = base_url + href
        else:
            full_link = href
        print(f"🔗 [SCRAPER] 링크: '{full_link}'")
        return full_link

    return None


def _create_contest_data(title, link, published_date):
    """공모전 데이터 생성"""
    return {
        "title": title,
        "link": link,
        "published": published_date.isoformat(),
        "scraper_type": "wevity_contest",
    }


def _process_single_contest(item, index, recent_titles, recent_links, kst):
    """단일 공모전 처리"""
    try:
        print(f"🔍 [SCRAPER] 공모전 {index+1} 처리 시작")

        # 제목 추출
        title_info = _extract_title_from_item(item, index)
        if not title_info:
            return None

        title, _ = title_info

        # 기존 공모전 확인 (제목 기준)
        if title in recent_titles:
            print(f"♻️ [SCRAPER] 기존 공모전 (스킵): {title[:30]}...")
            return None

        # 링크 추출
        link = _extract_link_from_item(item, index)
        if not link:
            return None

        # 기존 공모전 확인 (링크 기준)
        if link in recent_links:
            print(f"♻️ [SCRAPER] 기존 링크 (스킵): {link}")
            return None

        # 마감일 정보 추출 및 published 계산
        deadline = _extract_deadline_from_item(item, index)
        published = parse_date(deadline, kst) if deadline else datetime.now(kst)

        contest_data = _create_contest_data(title, link, published)

        # 30일 이내 필터링 (published 기준)
        thirty_days_ago = datetime.now(kst) - timedelta(days=30)
        published_date = datetime.fromisoformat(
            contest_data["published"].replace("Z", "+00:00")
        )

        if published_date >= thirty_days_ago:
            print(f"🆕 [SCRAPER] 새로운 공모전 추가: {title[:30]}...")
            return contest_data
        else:
            print(f"⏰ [SCRAPER] 30일 이전 공모전 제외: {title[:30]}...")
            return None

    except Exception as e:
        print(f"⚠️ [SCRAPER] 공모전 {index+1} 처리 중 오류: {e}")
        return None


def scrape_wevity_contest() -> Dict[str, Any]:
    """
    위비티 공모전을 스크래핑하고 새로운 공모전을 처리 (Playwright 기반)
    """
    url = "https://www.wevity.com/?c=find&s=1&gub=1&cidx=20&gbn=list"
    kst = pytz.timezone("Asia/Seoul")

    print(f"🌐 [SCRAPER] 스크래핑 시작 - URL: {url}")

    try:
        p, browser, page = _setup_browser()
        new_contests = []

        try:
            _navigate_to_main_page(page, url)
            items = _get_contest_items(page)

            if not items:
                print("❌ [SCRAPER] 공모전 항목을 찾을 수 없음")
                return {
                    "success": False,
                    "error": "공모전 항목을 찾을 수 없음",
                }

            # 기존 공모전 확인
            recent_notices = get_recent_notices("wevity_contest")
            recent_links = {notice.get("link") for notice in recent_notices}
            recent_titles = {notice.get("title") for notice in recent_notices}
            print(f"📋 [DB] 기존 공모전 수: {len(recent_notices)}")

            # 각 공모전 처리
            for i in range(len(items)):
                # 매번 새로운 요소 쿼리 (ElementHandle 무효화 대비)
                current_items = page.query_selector_all("ul.list li:not(.top)")
                if i >= len(current_items):
                    print(f"⚠️ [SCRAPER] 공모전 {i+1} 인덱스 초과")
                    continue

                item = current_items[i]
                contest_data = _process_single_contest(
                    item, i, recent_titles, recent_links, kst
                )

                if contest_data:
                    new_contests.append(contest_data)

        finally:
            browser.close()
            p.stop()

        print(f"📈 [SCRAPER] 새로운 공모전 수: {len(new_contests)}")
        saved_count = 0
        if new_contests:
            saved_count = save_notices_to_db(new_contests, "wevity_contest")
            print(f"💾 [SCRAPER] 저장 완료: {saved_count}개")

        result = {
            "success": True,
            "message": "위비티 공모전 스크래핑 완료",
            "total_found": len(items),
            "new_notices_count": len(new_contests),
            "saved_count": saved_count,
            "new_notices": new_contests,
        }

        print(f"🎉 [SCRAPER] 스크래핑 완료")
        return result

    except Exception as e:
        error_msg = f"스크래핑 중 오류: {str(e)}"
        print(f"❌ [SCRAPER] {error_msg}")
        send_slack_notification(error_msg, "wevity_contest")
        return {"success": False, "error": error_msg}


def parse_contest_from_element(element, kst) -> Dict[str, Any]:
    """HTML 요소에서 공모전 정보를 추출"""

    try:
        # 제목 추출
        title_tag = element.select_one("div.tit a")
        if not title_tag:
            return None

        title = title_tag.get_text(strip=True)
        # SPECIAL, IDEA 태그 제거
        title = re.sub(r"\s*<span[^>]*>.*?</span>", "", title)

        # 링크 추출
        link = title_tag.get("href")
        if link:
            # 상대 경로를 절대 경로로 변환
            if link.startswith("?"):
                base_url = "https://www.wevity.com/"
                link = base_url + link

        # 마감일 정보 추출
        day_element = element.select_one("div.day")
        deadline = day_element.get_text(strip=True) if day_element else None

        # 마감일 파싱하여 published_date 생성
        published = parse_date(deadline, kst) if deadline else datetime.now(kst)

        result = {
            "title": title,
            "link": link,
            "published": published.isoformat(),
            "scraper_type": "wevity_contest",
        }

        return result

    except Exception as e:
        print(f"❌ [PARSE] 공모전 파싱 중 오류: {e}")
        return None


def handler(event, context):
    """
    위비티 공모전 스크래퍼 Lambda Handler
    깔끔하고 독립적인 구현
    """

    print("🚀 [HANDLER] Lambda Handler 시작")

    try:
        # 동기 스크래퍼 실행
        result = scrape_wevity_contest()

        return {
            "statusCode": 200,
        }

    except Exception as e:
        error_msg = f"Lambda Handler 실행 중 오류: {str(e)}"
        print(f"❌ [HANDLER] {error_msg}")
        send_slack_notification(error_msg, "wevity_contest")
        return {
            "statusCode": 500,
        }
