import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from pymongo import MongoClient
from typing import List, Dict, Any
import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import urllib3

# SSL 경고 억제
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def fetch_page(url: str, timeout: int = 30) -> BeautifulSoup:
    """웹 페이지를 동기적으로 가져와 BeautifulSoup 객체로 반환"""

    try:
        print(f"🔍 [FETCH] 요청 시작: {url}")

        # requests를 사용한 단순한 HTTP 요청
        response = requests.get(
            url,
            timeout=timeout,
            verify=False,  # SSL 검증 비활성화
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
        )

        if response.status_code != 200:
            error_msg = f"페이지 요청 실패: {url}, 상태 코드: {response.status_code}"
            print(f"❌ [FETCH] {error_msg}")
            raise Exception(error_msg)

        # 응답 크기 제한
        if len(response.content) > 5 * 1024 * 1024:  # 5MB
            error_msg = f"응답이 너무 큽니다: {len(response.content)} bytes"
            print(f"⚠️ [FETCH] {error_msg}")
            raise Exception(error_msg)

        # 인코딩 처리
        try:
            html_text = response.content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                html_text = response.content.decode("euc-kr")
            except UnicodeDecodeError:
                html_text = response.content.decode("cp949", errors="replace")

        soup = BeautifulSoup(html_text, "html.parser")
        print(f"✅ [FETCH] 성공: {url}")
        return soup

    except requests.exceptions.Timeout:
        error_msg = f"타임아웃: {url}"
        print(f"❌ [FETCH] {error_msg}")
        raise Exception(error_msg)
    except Exception as e:
        error_msg = f"페이지 요청 중 오류: {e}"
        print(f"❌ [FETCH] {error_msg}")
        raise Exception(error_msg)


def get_recent_notices(collection_name: str) -> List[Dict[str, Any]]:
    """MongoDB에서 최근 공지사항들을 가져옴"""

    try:
        mongodb_uri = os.environ.get("MONGODB_URI")
        mongodb_database = os.environ.get("DB_NAME")

        if not mongodb_uri or not mongodb_database:
            print("❌ [DB] MongoDB 연결 정보가 없습니다")
            return []

        client = MongoClient(mongodb_uri)
        db = client[mongodb_database]
        collection = db[collection_name]

        # 최근 30일간의 공지사항만 가져오기 (성능 최적화)
        thirty_days_ago = datetime.now() - timedelta(days=40)

        # ISO 형식 문자열로 변환
        thirty_days_ago_iso = thirty_days_ago.isoformat()

        notices = list(
            collection.find(
                {"published": {"$gte": thirty_days_ago_iso}},
                {"title": 1, "link": 1, "_id": 0},
            )
        )
        client.close()
        return notices

    except Exception as e:
        error_msg = f"MongoDB에서 데이터 조회 중 오류: {e}"
        print(f"❌ [DB] {error_msg}")
        send_common_utils_error_notification(
            "get_recent_notices", error_msg, f"컬렉션: {collection_name}"
        )
        return []


def save_notices_to_db(notices: List[Dict[str, Any]], collection_name: str) -> int:
    """새로운 공지사항들을 MongoDB에 저장"""

    try:
        mongodb_uri = os.environ.get("MONGODB_URI")
        mongodb_database = os.environ.get("DB_NAME")

        if not mongodb_uri or not mongodb_database:
            print("❌ [DB] MongoDB 연결 정보가 없습니다")
            return 0

        client = MongoClient(mongodb_uri)
        db = client[mongodb_database]
        collection = db[collection_name]

        # 배치 인서트
        if notices:
            result = collection.insert_many(notices)
            inserted_count = len(result.inserted_ids)
        else:
            inserted_count = 0

        client.close()
        return inserted_count

    except Exception as e:
        error_msg = f"MongoDB에 데이터 저장 중 오류: {e}"
        print(f"❌ [DB] {error_msg}")
        send_common_utils_error_notification(
            "save_notices_to_db",
            error_msg,
            f"컬렉션: {collection_name}, 저장 시도 개수: {len(notices)}",
        )
        return 0


def send_slack_notification(message: str, scraper_type: str = "unknown") -> bool:
    """Slack으로 에러 알림을 보냄"""

    try:
        slack_token = os.environ.get("SLACK_BOT_TOKEN")
        channel_id = os.environ.get("SLACK_CHANNEL_ID")

        if not slack_token or not channel_id:
            print("❌ [SLACK] Slack 설정이 없습니다")
            return False

        client = WebClient(token=slack_token)

        # 에러 메시지 포맷팅
        formatted_message = f"🚨 *스크래퍼 에러 알림*\n\n*스크래퍼 타입:* {scraper_type}\n*에러 메시지:* {message}\n*발생 시간:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        response = client.chat_postMessage(
            channel=channel_id, text=formatted_message, parse="mrkdwn"
        )

        print(f"✅ [SLACK] 에러 알림 전송 성공: {response['ts']}")
        return True

    except SlackApiError as e:
        print(f"❌ [SLACK] Slack API 에러: {e.response['error']}")
        return False
    except Exception as e:
        print(f"❌ [SLACK] Slack 알림 전송 중 오류: {e}")
        return False


def send_common_utils_error_notification(
    method_name: str, error: str, additional_info: str = None
) -> bool:
    """common_utils.py의 메서드들에서 발생한 에러를 위한 통합 알림 함수"""

    message = f"Common Utils 에러\n*메서드:* {method_name}\n*에러:* {error}"
    if additional_info:
        message += f"\n*추가 정보:* {additional_info}"

    return send_slack_notification(message, f"common_utils_{method_name}")


# ===== 공통 스크래핑 유틸 =====
def setup_playwright_browser():
    """Playwright 브라우저/페이지 공통 설정"""
    try:
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
    except Exception as e:
        error_msg = f"Playwright 브라우저 설정 실패: {e}"
        print(f"❌ [SCRAPER] {error_msg}")
        raise


def get_recent_title_link_sets(collection_name: str):
    """최근 공지에서 제목/링크 세트와 원본 리스트를 함께 반환"""
    recent = get_recent_notices(collection_name)
    recent_titles = {n.get("title") for n in recent}
    recent_links = {n.get("link") for n in recent}
    return recent_titles, recent_links, recent


def _parse_iso_datetime(dt_str: str) -> datetime:
    """ISO 문자열을 datetime으로 안전하게 파싱 (Z 처리 포함)"""
    try:
        if not dt_str:
            return datetime.now()
        normalized = dt_str.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except Exception:
        return datetime.now()


def is_within_days(published_iso_str: str, days: int, tz) -> bool:
    """발행일이 최근 N일 이내인지 여부"""
    try:
        published_dt = _parse_iso_datetime(published_iso_str)
        if tz is not None and published_dt.tzinfo is None:
            # naive -> 지정된 타임존 로컬라이즈
            try:
                published_dt = tz.localize(published_dt)
            except Exception:
                pass
        threshold = (
            datetime.now(tz) if tz is not None else datetime.now()
        ) - timedelta(days=days)
        return published_dt >= threshold
    except Exception:
        # 파싱 오류 시 보수적으로 포함 처리
        return True
