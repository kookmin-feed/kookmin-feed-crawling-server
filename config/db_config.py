import logging
from pymongo import MongoClient
from config.env_loader import ENV
from template.notice_data import NoticeData
from utils.scraper_type import ScraperType
from utils.scraper_category import ScraperCategory

# 로거 설정
logger = logging.getLogger(__name__)

# 환경 변수 설정
IS_PROD = ENV["IS_PROD"]  # env_loader에서 가져옴


def get_database(db_name: str = None):
    """MongoDB 데이터베이스 연결을 반환합니다.

    Args:
        db_name (str, optional): 사용할 데이터베이스 이름.
            미지정시 환경변수의 DB_NAME 또는 기본값 사용
    """
    try:
        client = MongoClient(ENV["MONGODB_URI"])
        default_db = "dev-kookmin-feed" if not IS_PROD else "kookmin-feed"
        db_name = db_name or ENV["DB_NAME"] or default_db
        return client[db_name]
    except Exception as e:
        logger.error(f"DB 연결 중 오류 발생: {e}")
        raise


def get_collection(db_name: str = None, collection_name: str = None):
    """DB내 컬렉션 반환."""
    return get_database(db_name)[collection_name]


async def save_notice(notice: NoticeData, scraper_type: ScraperType):
    """공지사항을 DB에 저장합니다."""
    try:
        collection = get_collection(collection_name=scraper_type.get_collection_name())
        collection.insert_one(
            {
                "title": notice.title,
                "link": notice.link,
                "published": notice.published.isoformat(),
                "scraper_type": scraper_type.get_collection_name(),
            }
        )
    except Exception as e:
        logger.error(f"DB 저장 중 오류 발생: {e}")


def read_notice_list(notice_type: str = None, list_size: int = None):
    """공지사항 리스트 반환"""
    documents = None

    if list_size is None:
        documents = get_collection(collection_name=notice_type).find(
            sort=[("published", -1)]
        )
    else:
        documents = get_collection(collection_name=notice_type).find(
            sort=[("published", -1)]
        ).limit(list_size)

    doc_list = []

    for doc in documents:
        doc_list.append(doc)

    return doc_list


def save_scraper_categories():
    """ScraperCategory 데이터를 DB에 저장합니다."""
    try:
        collection = get_collection(db_name="scraper-metadata", collection_name="scraper-categories")
        for category in ScraperCategory:
            collection.update_one(
                {"name": category.name},
                {
                    "$set": {
                        "korean_name": category.korean_name,
                        "scraper_type_names": [scraper.name for scraper in category.scraper_types],
                    }
                },
                upsert=True,
            )
        logger.info("ScraperCategory 저장 또는 업데이트 완료")
        return True
    except Exception as e:
        logger.error(f"ScraperCategory 저장 또는 업데이트 중 오류 발생: {e}")
        return False


def save_scraper_type(scraper_type: ScraperType):
    """ScraperType 데이터를 DB에 저장합니다."""
    try:
        collection = get_collection(db_name="scraper-metadata", collection_name="scraper-types")
        collection.update_one(
            {"collection_name": scraper_type.get_collection_name()},
            {
                "$set": {
                    "type_name": scraper_type.name,
                    "korean_name": scraper_type.get_korean_name(),
                    "url": scraper_type.get_url(),
                    "scraper_class_name": scraper_type.get_scraper_class_name(),
                }
            },
            upsert=True,
        )
        logger.info(f"ScraperType 저장 또는 업데이트 완료: {scraper_type.get_korean_name()}")
        return True
    except Exception as e:
        logger.error(f"ScraperType 저장 또는 업데이트 중 오류 발생: {e}")
        return False


def close_database():
    """데이터베이스 연결을 종료합니다."""
    try:
        client = MongoClient(ENV["MONGODB_URI"])
        client.close()
    except Exception as e:
        logger.error(f"DB 연결 종료 중 오류 발생: {e}")
