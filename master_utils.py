import json
import os
from datetime import datetime
from pymongo import MongoClient
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


def send_master_handler_error_notification(
    function_name: str, error: str, additional_info: str = None
) -> bool:
    """master_handler.py에서 발생한 에러를 위한 전용 알림 함수"""

    try:
        slack_token = os.environ.get("SLACK_BOT_TOKEN")
        channel_id = os.environ.get("SLACK_CHANNEL_ID")

        if not slack_token or not channel_id:
            print("❌ [SLACK] Slack 설정이 없습니다")
            return False

        client = WebClient(token=slack_token)

        # 에러 메시지 포맷팅
        message = f"Master Handler 에러\n*함수명:* {function_name}\n*에러:* {error}"
        if additional_info:
            message += f"\n*추가 정보:* {additional_info}"

        formatted_message = f"🚨 *Master Handler 에러 알림*\n\n{message}\n*발생 시간:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

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


def load_scraper_types():
    """스크래퍼 타입 JSON 파일을 로드합니다."""
    try:
        with open("metadata/scraper_types.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("scraper_types", {})
    except Exception as e:
        error_msg = f"스크래퍼 타입 파일 로드 실패: {e}"
        print(f"❌ [LOAD] {error_msg}")
        send_master_handler_error_notification("load_scraper_types", error_msg)
        return {}


def load_scraper_categories():
    """스크래퍼 카테고리 JSON 파일을 로드합니다."""
    try:
        with open("metadata/scraper_categories.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("scraper_categories", {})
    except Exception as e:
        error_msg = f"스크래퍼 카테고리 파일 로드 실패: {e}"
        print(f"❌ [LOAD] {error_msg}")
        send_master_handler_error_notification("load_scraper_categories", error_msg)
        return {}


def get_database(db_name: str = None):
    """MongoDB 데이터베이스 연결을 반환합니다."""
    try:
        mongodb_uri = os.environ.get("MONGODB_URI")
        if not mongodb_uri:
            print("❌ [DB] MongoDB URI가 설정되지 않았습니다")
            return None

        client = MongoClient(mongodb_uri)
        default_db = "dev-kookmin-feed"
        db_name = db_name or os.environ.get("DB_NAME") or default_db
        return client[db_name]
    except Exception as e:
        error_msg = f"DB 연결 중 오류 발생: {e}"
        print(f"❌ [DB] {error_msg}")
        send_master_handler_error_notification("get_database", error_msg)
        return None


def get_collection(db_name: str = None, collection_name: str = None):
    """DB내 컬렉션 반환."""
    db = get_database(db_name)
    if db is None:
        return None
    return db[collection_name]


def save_scraper_categories_to_db(scraper_categories):
    """ScraperCategory 데이터를 DB에 저장합니다."""
    try:
        collection = get_collection(
            db_name="scraper-metadata", collection_name="scraper-categories"
        )
        if collection is None:
            print("❌ [DB] 컬렉션을 가져올 수 없습니다")
            return False

        for category_name, category_info in scraper_categories.items():
            collection.update_one(
                {"name": category_name},
                {
                    "$set": {
                        "korean_name": category_info.get("korean_name", ""),
                        "scraper_type_names": category_info.get("scraper_types", []),
                    }
                },
                upsert=True,
            )
        print("✅ [DB] ScraperCategory 저장 또는 업데이트 완료")
        return True
    except Exception as e:
        error_msg = f"ScraperCategory 저장 또는 업데이트 중 오류 발생: {e}"
        print(f"❌ [DB] {error_msg}")
        send_master_handler_error_notification(
            "save_scraper_categories_to_db", error_msg
        )
        return False


def save_scraper_types_to_db(scraper_types, valid_scrapers):
    """유효한 스크래퍼 타입들을 DB에 저장합니다."""
    try:
        collection = get_collection(
            db_name="scraper-metadata", collection_name="scraper-types"
        )
        if collection is None:
            print("❌ [DB] 컬렉션을 가져올 수 없습니다")
            return False

        saved_count = 0
        for scraper_type, scraper_info in scraper_types.items():
            # 유효한 스크래퍼만 저장
            if scraper_info.get("scraper_lambda_function_name") in valid_scrapers:
                collection.update_one(
                    {"collection_name": scraper_type.lower()},
                    {
                        "$set": {
                            "type_name": scraper_type,
                            "korean_name": scraper_info.get("korean_name", ""),
                            "url": scraper_info.get("url", ""),
                            "scraper_class_name": scraper_info.get(
                                "scraper_class_name", ""
                            ),
                            "scraper_lambda_function_name": scraper_info.get(
                                "scraper_lambda_function_name", ""
                            ),
                        }
                    },
                    upsert=True,
                )
                saved_count += 1
                print(
                    f"✅ [DB] ScraperType 저장: {scraper_info.get('korean_name', '')}"
                )

        print(f"✅ [DB] ScraperType 저장 또는 업데이트 완료: {saved_count}개")
        return True
    except Exception as e:
        error_msg = f"ScraperType 저장 또는 업데이트 중 오류 발생: {e}"
        print(f"❌ [DB] {error_msg}")
        send_master_handler_error_notification("save_scraper_types_to_db", error_msg)
        return False


def find_category_by_scraper_type(scraper_type, scraper_categories):
    """스크래퍼 타입이 속한 카테고리를 찾습니다."""
    for category_name, category_info in scraper_categories.items():
        if scraper_type in category_info.get("scraper_types", []):
            return category_name
    return None


def generate_actual_function_names(expected_function_name):
    """환경별 접두사를 포함한 실제 Lambda 함수 이름들을 생성합니다."""
    # 환경별 접두사 (실제 환경에 맞게 조정 필요)
    prefixes = ["", "dev-", "prod-"]
    return [f"{prefix}{expected_function_name}" for prefix in prefixes]
