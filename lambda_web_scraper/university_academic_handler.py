import json
import asyncio
from datetime import datetime
import pytz
from typing import Dict, Any
from common_utils import fetch_page, get_recent_notices, save_notices_to_db


def handler(event, context):
    """
    대학 학사공지 스크래퍼 Lambda Handler
    깔끔하고 독립적인 구현
    """

    print("🚀 [HANDLER] Lambda Handler 시작")

    try:
        # 비동기 스크래퍼 실행
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(scrape_university_academic())
        finally:
            loop.close()

        return {
            "statusCode": 200,
            "body": json.dumps(result, ensure_ascii=False, default=str),
        }

    except Exception as e:
        print(f"❌ [HANDLER] 오류 발생: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps(
                {"error": f"Lambda Handler 실행 중 오류: {str(e)}"}, ensure_ascii=False
            ),
        }


async def scrape_university_academic() -> Dict[str, Any]:
    """
    대학 학사공지를 스크래핑하고 새로운 공지사항을 처리
    """

    url = "https://cs.kookmin.ac.kr/news/kookmin/academic/"
    kst = pytz.timezone("Asia/Seoul")

    print(f"🌐 [SCRAPER] 스크래핑 시작 - URL: {url}")

    try:
        # 웹페이지 가져오기
        soup = await fetch_page(url)
        if not soup:
            print("❌ [SCRAPER] 웹페이지 가져오기 실패")
            return {"success": False, "error": "웹페이지를 가져올 수 없습니다"}

        # 공지사항 목록 요소들 가져오기
        elements = soup.select(".list-tbody .normal-bg, .list-tbody .notice-bg")
        print(f"📊 [SCRAPER] 발견된 공지사항 수: {len(elements)}")

        # 기존 공지사항 확인 (MongoDB에서)
        recent_notices = get_recent_notices("university_academic")
        recent_links = {notice.get("link") for notice in recent_notices}
        recent_titles = {notice.get("title") for notice in recent_notices}

        # 새로운 공지사항 파싱
        new_notices = []

        for element in elements:
            notice = parse_notice_from_element(element, kst)
            if notice:
                # 중복 확인
                if (
                    notice["link"] not in recent_links
                    and notice["title"] not in recent_titles
                ):
                    new_notices.append(notice)
                    print(f"🆕 [SCRAPER] 새로운 공지사항: {notice['title'][:30]}...")

        print(f"📈 [SCRAPER] 새로운 공지사항 수: {len(new_notices)}")

        # 새로운 공지사항을 MongoDB에 저장
        saved_count = 0
        if new_notices:
            saved_count = save_notices_to_db(new_notices, "university_academic")
            print(f"💾 [SCRAPER] 저장 완료: {saved_count}개")

        result = {
            "success": True,
            "message": f"대학 학사공지 스크래핑 완료",
            "total_found": len(elements),
            "new_notices_count": len(new_notices),
            "saved_count": saved_count,
            "new_notices": new_notices,
        }

        print(f"🎉 [SCRAPER] 스크래핑 완료")
        return result

    except Exception as e:
        print(f"❌ [SCRAPER] 스크래핑 중 오류: {str(e)}")
        return {"success": False, "error": f"스크래핑 중 오류: {str(e)}"}


def parse_notice_from_element(row, kst) -> Dict[str, Any]:
    """HTML 요소에서 학사공지 정보를 추출"""

    try:
        title_tag = row.select_one(".subject a")
        if not title_tag:
            return None

        title = title_tag.text.strip()
        link = title_tag["href"]

        # 상대 링크를 절대 링크로 변환
        if not link.startswith("http"):
            link = f"https://cs.kookmin.ac.kr/news/kookmin/academic/{link}"

        # 날짜 추출
        date_element = row.select_one(".date")
        if not date_element:
            return None

        date_str = date_element.text.strip()
        published = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=kst)

        result = {
            "title": title,
            "link": link,
            "published": published,
            "scraper_type": "university_academic",
            "korean_name": "대학 학사공지",
        }

        return result

    except Exception as e:
        print(f"❌ [PARSE] 공지사항 파싱 중 오류: {e}")
        return None
