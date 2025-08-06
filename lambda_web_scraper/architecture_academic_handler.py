import json

import re
from datetime import datetime, timedelta
import pytz
from typing import Dict, Any
from bs4 import BeautifulSoup
from common_utils import (
    fetch_page,
    get_recent_notices,
    save_notices_to_db,
    send_slack_notification,
)


def handler(event, context):
    """
    건축대학 학사공지 스크래퍼 Lambda Handler
    깔끔하고 독립적인 구현
    """

    print("🚀 [HANDLER] Lambda Handler 시작")

    try:
        # 동기 스크래퍼 실행
        result = scrape_architecture_academic()

        return {
            "statusCode": 200,
            "body": json.dumps(result, ensure_ascii=False, default=str),
        }

    except Exception as e:
        error_msg = f"Lambda Handler 실행 중 오류: {str(e)}"
        print(f"❌ [HANDLER] {error_msg}")
        send_slack_notification(error_msg, "architecture_academic")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": error_msg}, ensure_ascii=False),
        }


def scrape_architecture_academic() -> Dict[str, Any]:
    """
    건축대학 학사공지를 스크래핑하고 새로운 공지사항을 처리
    """

    url = "https://archi.kookmin.ac.kr/life/notice/"
    kst = pytz.timezone("Asia/Seoul")

    print(f"🌐 [SCRAPER] 스크래핑 시작 - URL: {url}")

    try:
        # 웹페이지 가져오기
        soup = fetch_page(url)

        # 공지사항 목록 요소들 가져오기
        elements = soup.select(".board-list-type01 li")
        print(f"📊 [SCRAPER] 발견된 공지사항 수: {len(elements)}")

        # 기존 공지사항 확인 (MongoDB에서)
        recent_notices = get_recent_notices("architecture_academic")
        recent_links = {notice.get("link") for notice in recent_notices}
        recent_titles = {notice.get("title") for notice in recent_notices}

        # 새로운 공지사항 파싱
        new_notices = []

        for element in elements:
            notice = parse_notice_from_element(element, kst, url)
            if notice:
                # 30일 이내의 데이터만 필터링
                thirty_days_ago = datetime.now(kst) - timedelta(days=30)
                if notice["published"] >= thirty_days_ago:
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
            saved_count = save_notices_to_db(new_notices, "architecture_academic")
            print(f"💾 [SCRAPER] 저장 완료: {saved_count}개")

        result = {
            "success": True,
            "message": f"건축대학 학사공지 스크래핑 완료",
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
        send_slack_notification(error_msg, "architecture_academic")
        return {"success": False, "error": error_msg}


def parse_notice_from_element(element, kst, base_url) -> Dict[str, Any]:
    """HTML 요소에서 건축대학 공지사항 정보를 추출"""

    try:
        # 공지사항 링크 태그 찾기
        link_tag = element.select_one("a")
        if not link_tag:
            return None

        # 제목 추출
        title_tag = element.select_one(".borad-list-tit")
        if not title_tag:
            return None

        title = title_tag.text.strip()

        # 링크 생성
        href = link_tag.get("href", "")
        link = f"{base_url}{href}"

        # 날짜 추출
        date_tag = element.select_one(".board-list-date")
        if not date_tag:
            return None

        date = date_tag.text.strip()
        published = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=kst)

        result = {
            "title": title,
            "link": link,
            "published": published,
            "scraper_type": "architecture_academic",
            "korean_name": "건축대학 학사공지",
        }

        return result

    except Exception as e:
        print(f"❌ [PARSE] 공지사항 파싱 중 오류: {e}")
        return None 