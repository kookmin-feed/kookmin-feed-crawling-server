import json

from datetime import datetime, timedelta
import pytz
from typing import Dict, Any
from common_utils import (
    fetch_page,
    get_recent_notices,
    save_notices_to_db,
    send_slack_notification,
)


def handler(event, context):
    """
    대학 장학공지 스크래퍼 Lambda Handler
    깔끔하고 독립적인 구현
    """

    print("🚀 [HANDLER] Lambda Handler 시작")

    try:
        # 동기 스크래퍼 실행
        result = scrape_university_scholarship()

        return {
            "statusCode": 200,
        }

    except Exception as e:
        error_msg = f"Lambda Handler 실행 중 오류: {str(e)}"
        print(f"❌ [HANDLER] {error_msg}")
        send_slack_notification(error_msg, "university_scholarship")
        return {
            "statusCode": 500,
        }


def scrape_university_scholarship() -> Dict[str, Any]:
    """
    대학 장학공지를 스크래핑하고 새로운 공지사항을 처리
    """

    url = "https://cs.kookmin.ac.kr/news/kookmin/scholarship/"
    kst = pytz.timezone("Asia/Seoul")

    print(f"🌐 [SCRAPER] 스크래핑 시작 - URL: {url}")

    try:
        # 웹페이지 가져오기
        soup = fetch_page(url)

        # 공지사항 목록 요소들 가져오기
        elements = soup.select(".list-tbody ul")
        print(f"📊 [SCRAPER] 발견된 공지사항 수: {len(elements)}")

        # 기존 공지사항 확인 (MongoDB에서)
        recent_notices = get_recent_notices("university_scholarship")
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
            saved_count = save_notices_to_db(new_notices, "university_scholarship")
            print(f"💾 [SCRAPER] 저장 완료: {saved_count}개")

        result = {
            "success": True,
            "message": f"대학 장학공지 스크래핑 완료",
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
        send_slack_notification(error_msg, "university_scholarship")
        return {"success": False, "error": error_msg}


def parse_notice_from_element(element, kst) -> Dict[str, Any]:
    """HTML 요소에서 장학공지 정보를 추출"""

    try:
        # 공지사항 여부 확인
        is_notice = element.select_one(".notice") is not None

        # 제목과 링크 추출
        title_element = element.select_one(".subject a")
        if not title_element:
            return None

        title = title_element.get_text(strip=True)
        relative_link = title_element.get("href", "")
        link = f"https://cs.kookmin.ac.kr/news/kookmin/scholarship/{relative_link}"

        # 날짜 추출
        date_element = element.select_one(".date")
        if not date_element:
            return None

        date_str = date_element.get_text(strip=True)

        # 다양한 날짜 형식 처리
        try:
            # YYYY-MM-DD 형식
            published = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=kst)
        except ValueError:
            try:
                # YYYY.MM.DD 형식
                published = datetime.strptime(date_str, "%Y.%m.%d").replace(tzinfo=kst)
            except ValueError:
                # YY.MM.DD 형식
                published = datetime.strptime(date_str, "%y.%m.%d").replace(tzinfo=kst)

        result = {
            "title": title,
            "link": link,
            "published": published.isoformat(),
            "scraper_type": "university_scholarship",
        }

        return result

    except Exception as e:
        print(f"❌ [PARSE] 공지사항 파싱 중 오류: {e}")
        return None
