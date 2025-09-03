from datetime import datetime, timedelta
import pytz
from typing import Dict, Any
import re
import os
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from common_utils import (
    get_recent_notices,
    save_notices_to_db,
    send_slack_notification,
)


def fetch_page_with_playwright(url: str, timeout: int = 30000) -> BeautifulSoup:
    """Playwright를 사용하여 동적 콘텐츠가 로드된 페이지를 가져와 BeautifulSoup 객체로 반환"""

    try:
        print(f"🔍 [PLAYWRIGHT] 요청 시작: {url}")

        # AWS Lambda 환경 감지
        is_lambda = bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))

        # Lambda 환경에서 Playwright 설정
        if is_lambda:
            # Lambda 환경에서는 /tmp에 브라우저 바이너리가 필요
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "/opt/playwright"

        with sync_playwright() as p:
            # Lambda 환경에 맞는 브라우저 설정
            if is_lambda:
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
            else:
                # 로컬 환경
                browser = p.chromium.launch(headless=True)

            page = browser.new_page()

            # User-Agent 설정
            page.set_extra_http_headers(
                {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                }
            )

            # 페이지 이동 및 로딩 대기
            page.goto(url, timeout=timeout)

            # Angular 컴포넌트가 로드될 때까지 대기
            # 공지사항 테이블이 나타날 때까지 기다림
            try:
                page.wait_for_selector("table.ikc-bulletins", timeout=10000)
                print("✅ [PLAYWRIGHT] 테이블 로딩 완료")
            except Exception as e:
                print(f"⚠️ [PLAYWRIGHT] 테이블 로딩 대기 실패: {e}")
                # 테이블이 없어도 페이지 콘텐츠는 가져와 봄

            # 추가적으로 조금 더 대기 (동적 콘텐츠 완전 로딩)
            page.wait_for_timeout(2000)

            # HTML 콘텐츠 가져오기
            html_content = page.content()
            browser.close()

            print(f"✅ [PLAYWRIGHT] 성공: {url}")

            # BeautifulSoup 객체로 파싱
            soup = BeautifulSoup(html_content, "html.parser")
            return soup

    except Exception as e:
        error_msg = f"Playwright 페이지 요청 실패: {url}, 오류: {str(e)}"
        print(f"❌ [PLAYWRIGHT] {error_msg}")
        raise Exception(error_msg)


def handler(event, context):
    """
    성곡도서관 일반공지 스크래퍼 Lambda Handler
    """

    print("🚀 [HANDLER] Lambda Handler 시작 - 성곡도서관 일반공지")

    try:
        # 동기 스크래퍼 실행
        result = scrape_library_general()

        return {
            "statusCode": 200,
        }

    except Exception as e:
        error_msg = f"Lambda Handler 실행 중 오류: {str(e)}"
        print(f"❌ [HANDLER] {error_msg}")
        send_slack_notification(error_msg, "library_general")
        return {
            "statusCode": 500,
        }


def scrape_library_general() -> Dict[str, Any]:
    """
    성곡도서관 일반공지를 스크래핑하고 새로운 공지사항을 처리
    """

    url = "https://lib.kookmin.ac.kr/library-guide/notice"
    kst = pytz.timezone("Asia/Seoul")

    print(f"🌐 [SCRAPER] 스크래핑 시작 - URL: {url}")

    try:
        # 웹페이지 가져오기 (Playwright 사용)
        soup = fetch_page_with_playwright(url)

        # 공지사항 목록 요소들 가져오기
        elements = soup.select("table.ikc-bulletins tbody tr.ng-star-inserted")
        print(f"📊 [SCRAPER] 발견된 공지사항 수: {len(elements)}")

        # 기존 공지사항 확인 (MongoDB에서)
        recent_notices = get_recent_notices("library_general")
        recent_links = {notice.get("link") for notice in recent_notices}
        recent_titles = {notice.get("title") for notice in recent_notices}

        # 새로운 공지사항 파싱
        new_notices = []

        for element in elements:
            notice = parse_notice_from_element(element, kst)
            if notice:
                # 30일 이내의 데이터만 필터링
                thirty_days_ago = datetime.now(kst) - timedelta(days=30)
                published_date = datetime.fromisoformat(
                    notice["published"].replace("Z", "+00:00")
                )
                if published_date >= thirty_days_ago:
                    # 중복 확인
                    if (
                        notice["link"] not in recent_links
                        and notice["title"] not in recent_titles
                    ):
                        new_notices.append(notice)
                        print(
                            f"🆕 [SCRAPER] 새로운 공지사항: {notice['title'][:30]}..."
                        )
                else:
                    print(
                        f"⏰ [SCRAPER] 30일 이전 공지사항 제외: {notice['title'][:30]}..."
                    )

        print(f"📈 [SCRAPER] 새로운 공지사항 수: {len(new_notices)}")

        # 새로운 공지사항을 MongoDB에 저장
        saved_count = 0
        if new_notices:
            saved_count = save_notices_to_db(new_notices, "library_general")
            print(f"💾 [SCRAPER] 저장 완료: {saved_count}개")

        result = {
            "success": True,
            "message": f"성곡도서관 일반공지 스크래핑 완료",
            "total_found": len(elements),
            "new_notices_count": len(new_notices),
            "saved_count": saved_count,
            "new_notices": new_notices,
        }

        print(f"🎉 [SCRAPER] 스크래핑 완료")
        return result

    except Exception as e:
        error_msg = f"스크래핑 중 오류: {str(e)}"
        print(f"❌ [SCRAPER] {error_msg}")
        send_slack_notification(error_msg, "library_general")
        return {"success": False, "error": error_msg}


def parse_notice_from_element(row, kst) -> Dict[str, Any]:
    """HTML 요소에서 성곡도서관 공지 정보를 추출"""

    try:
        # 순번 추출
        index_element = row.select_one(".ikc-bulletins-index span")
        if not index_element:
            return None

        notice_index = index_element.text.strip()

        # 제목 추출
        title_element = row.select_one(".ikc-bulletins-title span")
        if not title_element:
            return None

        title = title_element.text.strip()

        # 링크 생성 (상세 페이지 링크가 없으므로 메인 페이지 + 순번으로 구성)
        base_url = "https://lib.kookmin.ac.kr/library-guide/notice"
        link = f"{base_url}#{notice_index}"

        # 날짜 추출 - 작성자 정보에서 날짜 부분 찾기
        date_elements = row.select(".ikc-bulletins-properties li span")
        date_str = None

        # date_elements: [작성자, 날짜, 조회수] 형태
        if len(date_elements) >= 2:
            date_text = date_elements[1].text.strip()

            # "N월 N일" 패턴 확인
            if re.match(r"\d{1,2}월\s+\d{1,2}일", date_text):
                # "N월 N일" 형식을 현재 연도와 결합
                month_day = date_text.replace("월", "").replace("일", "").strip()
                try:
                    month, day = month_day.split()
                    current_year = datetime.now(kst).year
                    date_str = f"{current_year}-{int(month):02d}-{int(day):02d}"
                except ValueError:
                    print(f"❌ [PARSE] 날짜 파싱 실패: {date_text}")
                    date_str = datetime.now(kst).strftime("%Y-%m-%d")
            # "오전/오후 시:분" 패턴도 확인 (혹시 모르니)
            elif re.match(r"(오전|오후)\s+\d{1,2}:\d{2}", date_text):
                # 오늘 날짜로 설정
                date_str = datetime.now(kst).strftime("%Y-%m-%d")
            else:
                print(f"⚠️ [PARSE] 알 수 없는 날짜 형식: {date_text}")
                date_str = datetime.now(kst).strftime("%Y-%m-%d")
        else:
            print(f"⚠️ [PARSE] 날짜 요소 부족: {len(date_elements)}개")
            date_str = datetime.now(kst).strftime("%Y-%m-%d")

        published = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=kst)

        result = {
            "title": title,
            "link": link,
            "published": published.isoformat(),
            "scraper_type": "library_general",
        }

        return result

    except Exception as e:
        print(f"❌ [PARSE] 공지사항 파싱 중 오류: {e}")
        return None
