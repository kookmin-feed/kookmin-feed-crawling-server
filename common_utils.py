import aiohttp
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from pymongo import MongoClient
from typing import List, Dict, Any
import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


async def fetch_page(url: str) -> BeautifulSoup:
    """웹 페이지를 비동기적으로 가져와 BeautifulSoup 객체로 반환"""

    try:
        # SSL 검증 비활성화를 위한 설정
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    print(
                        f"❌ [FETCH] 페이지 요청 실패: {url}, 상태 코드: {response.status}"
                    )
                    return None

                html = await response.read()

                # 인코딩 처리
                try:
                    html_text = html.decode("utf-8")
                except UnicodeDecodeError:
                    try:
                        html_text = html.decode("euc-kr")
                    except UnicodeDecodeError:
                        html_text = html.decode("cp949", errors="replace")

                soup = BeautifulSoup(html_text, "html.parser")
                return soup

    except Exception as e:
        error_msg = f"페이지 요청 중 오류: {e}"
        print(f"❌ [FETCH] {error_msg}")
        send_common_utils_error_notification("fetch_page", error_msg, f"URL: {url}")
        return None


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

        notices = list(
            collection.find(
                {"published": {"$gte": thirty_days_ago}},
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
