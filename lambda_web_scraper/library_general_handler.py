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
        # "9월 4일" 형식 파싱
        if "월" in date_str and "일" in date_str:
            month_day_match = re.search(r"(\d{1,2})월\s*(\d{1,2})일", date_str)
            if month_day_match:
                month = int(month_day_match.group(1))
                day = int(month_day_match.group(2))
                current_year = datetime.now(kst).year
                return kst.localize(datetime(current_year, month, day))

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
    """메인 페이지로 이동 및 테이블 로딩 대기"""
    page.goto(url, timeout=30000)
    page.wait_for_selector("table.ikc-bulletins", timeout=10000)
    page.wait_for_timeout(2000)


def _get_notice_rows(page):
    """공지사항 행들을 가져오기 (최신 10개만)"""
    rows = page.query_selector_all("table.ikc-bulletins tbody tr.ng-star-inserted")
    rows = rows[:10]  # 최신순으로 10개만 처리
    print(f"📊 [SCRAPER] 발견된 공지사항 수: {len(rows)} (최신 10개만 처리)")
    return rows


def _extract_title_from_row(row, index):
    """행에서 제목 추출"""
    title_element = row.query_selector("td:nth-child(2) span")
    if not title_element:
        print(f"⚠️ [SCRAPER] 공지사항 {index+1} 제목 요소를 찾을 수 없음")
        return None

    title = title_element.evaluate("el => el.textContent").strip()
    print(f"📰 [SCRAPER] 제목: '{title}'")
    return title, title_element


def _extract_date_from_detail_page(page, kst):
    """상세 페이지에서 날짜 정보 추출"""
    page.wait_for_timeout(2000)

    date_text = ""
    properties_elements = page.query_selector_all("ul.ikc-bulletin-properties li span")

    if len(properties_elements) >= 2:
        date_text = properties_elements[1].text_content().strip()

        # 시간 형식인지 확인 ("오전 9:14", "오후 2:30" 등)
        if re.match(r"(오전|오후)\s+\d{1,2}:\d{2}", date_text):
            date_text = datetime.now(kst).strftime("%m월 %d일")
        elif not re.match(r"\d{1,2}월\s+\d{1,2}일", date_text):
            date_text = datetime.now(kst).strftime("%m월 %d일")
    else:
        date_text = datetime.now(kst).strftime("%m월 %d일")

    return parse_date(date_text, kst)


def _create_notice_data(title, link, published_date):
    """공지사항 데이터 생성"""
    return {
        "title": title,
        "link": link,
        "published": published_date.isoformat(),
        "scraper_type": "library_general",
    }


def _return_to_main_page(page, url):
    """메인 페이지로 돌아가기"""
    page.goto(url, timeout=30000)
    page.wait_for_selector("table.ikc-bulletins", timeout=10000)
    page.wait_for_timeout(1000)


def _process_single_notice(page, row, index, url, recent_titles, recent_links, kst):
    """단일 공지사항 처리"""
    try:
        print(f"🔍 [SCRAPER] 공지사항 {index+1} 처리 시작")

        # 제목 추출
        title_info = _extract_title_from_row(row, index)
        if not title_info:
            return None

        title, title_element = title_info

        # 기존 공지사항 확인
        if title in recent_titles:
            print(f"♻️ [SCRAPER] 기존 공지사항 (스킵): {title[:30]}...")
            return None

        # 제목 클릭하여 상세 페이지로 이동
        title_element.click()
        page.wait_for_timeout(3000)
        actual_link = page.url

        # 링크 중복 확인
        if actual_link in recent_links:
            print(f"♻️ [SCRAPER] 기존 링크 (스킵): {actual_link}")
            _return_to_main_page(page, url)
            return None

        # 상세 페이지에서 날짜 추출
        try:
            published = _extract_date_from_detail_page(page, kst)
            notice_data = _create_notice_data(title, actual_link, published)

            # 30일 이내 필터링
            thirty_days_ago = datetime.now(kst) - timedelta(days=30)
            published_date = datetime.fromisoformat(
                notice_data["published"].replace("Z", "+00:00")
            )

            if published_date >= thirty_days_ago:
                print(f"🆕 [SCRAPER] 새로운 공지사항 추가: {title[:30]}...")
                return notice_data
            else:
                print(f"⏰ [SCRAPER] 30일 이전 공지사항 제외: {title[:30]}...")
                return None

        except Exception as e:
            print(f"⚠️ [SCRAPER] 상세 정보 추출 실패: {e}")
            notice_data = _create_notice_data(title, actual_link, datetime.now(kst))
            print(f"🆕 [SCRAPER] 기본 데이터로 공지사항 추가: {title[:30]}...")
            return notice_data

    except Exception as e:
        print(f"⚠️ [SCRAPER] 공지사항 {index+1} 처리 중 오류: {e}")
        return None
    finally:
        _return_to_main_page(page, url)


def _save_notices_to_db(new_notices):
    """새로운 공지사항들을 DB에 저장"""
    saved_count = 0
    if new_notices:
        print(f"💾 [DB] 저장 시도할 공지사항 수: {len(new_notices)}")
        saved_count = save_notices_to_db(new_notices, "library_general")
        print(f"💾 [DB] 실제 저장된 공지사항 수: {saved_count}")

        if saved_count != len(new_notices):
            print(f"⚠️ [DB] 저장 실패: 시도 {len(new_notices)}개, 성공 {saved_count}개")
    else:
        print("ℹ️ [DB] 새로운 공지사항이 없어 저장하지 않음")

    return saved_count


def scrape_library_general() -> Dict[str, Any]:
    """
    성곡도서관 일반공지 스크래핑 함수
    클릭 기반 스크래핑을 사용하여 실제 링크와 내용을 추출
    """
    url = "https://lib.kookmin.ac.kr/library-guide/notice"
    kst = pytz.timezone("Asia/Seoul")

    print(f"🌐 [SCRAPER] 스크래핑 시작 - URL: {url}")

    try:
        p, browser, page = _setup_browser()
        new_notices = []

        try:
            _navigate_to_main_page(page, url)
            rows = _get_notice_rows(page)

            if not rows:
                print("❌ [SCRAPER] 공지사항 행을 찾을 수 없음")
                return {
                    "statusCode": 500,
                    "body": {"message": "공지사항을 찾을 수 없음"},
                }

            # 기존 공지사항 확인
            recent_notices = get_recent_notices("library_general")
            recent_links = {notice.get("link") for notice in recent_notices}
            recent_titles = {notice.get("title") for notice in recent_notices}
            print(f"📋 [DB] 기존 공지사항 수: {len(recent_notices)}")

            # 각 공지사항 처리
            for i in range(len(rows)):
                # 매번 새로운 요소 쿼리 (ElementHandle 무효화 문제 해결)
                current_rows = page.query_selector_all(
                    "table.ikc-bulletins tbody tr.ng-star-inserted"
                )
                if i >= len(current_rows):
                    print(f"⚠️ [SCRAPER] 공지사항 {i+1} 인덱스 초과")
                    continue

                row = current_rows[i]
                notice_data = _process_single_notice(
                    page, row, i, url, recent_titles, recent_links, kst
                )

                if notice_data:
                    new_notices.append(notice_data)

        finally:
            browser.close()
            p.stop()

        print(f"📈 [SCRAPER] 새로운 공지사항 수: {len(new_notices)}")
        saved_count = _save_notices_to_db(new_notices)

        return {
            "statusCode": 200,
            "body": {
                "message": "스크래핑 완료",
                "scraped_count": len(rows),
                "new_count": len(new_notices),
                "saved_count": saved_count,
            },
        }

    except Exception as e:
        error_msg = f"스크래핑 중 오류: {str(e)}"
        print(f"❌ [SCRAPER] {error_msg}")
        send_slack_notification(error_msg, "library_general")
        raise e


def handler(event, context):
    """
    AWS Lambda 핸들러 함수
    """
    print("🚀 [HANDLER] Lambda Handler 시작 - 성곡도서관 일반공지")

    try:
        result = scrape_library_general()
        return result
    except Exception as e:
        error_msg = f"Lambda 핸들러 오류: {str(e)}"
        print(f"❌ [HANDLER] {error_msg}")
        return {
            "statusCode": 500,
            "body": {"message": error_msg},
        }
