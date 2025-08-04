import aiohttp
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from pymongo import MongoClient
from typing import List, Dict, Any
import os


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
        print(f"❌ [FETCH] 페이지 요청 중 오류: {e}")
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
        thirty_days_ago = datetime.now() - timedelta(days=90)

        notices = list(
            collection.find(
                {"published": {"$gte": thirty_days_ago}},
                {"title": 1, "link": 1, "_id": 0},
            )
        )
        client.close()
        return notices

    except Exception as e:
        print(f"❌ [DB] MongoDB에서 데이터 조회 중 오류: {e}")
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
        print(f"❌ [DB] MongoDB에 데이터 저장 중 오류: {e}")
        return 0
