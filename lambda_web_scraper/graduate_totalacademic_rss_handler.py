import feedparser
from datetime import datetime, timedelta
from urllib.parse import urljoin
import pytz
from typing import Dict, Any

from common_utils import (
    fetch_page,
    get_recent_notices,
    save_notices_to_db,
    send_slack_notification,
)

BASE_URL = "https://gds.kookmin.ac.kr/information/epartmentnotice/"


def handler(event, context):
    """
    대학원 전체학과게시판공지 RSS 스크래퍼 Lambda Handler
    """

    print("🚀 [HANDLER] 대학원 전체학과게시판공지 RSS 스크래퍼 Lambda Handler 시작")

    try:
        # 동기 스크래퍼 실행
        result = scrape_graduate_totalacademic_rss()

        return {
            "statusCode": 200,
        }

    except Exception as e:
        error_msg = f"Lambda Handler 실행 중 오류: {str(e)}"
        print(f"❌ [HANDLER] {error_msg}")
        send_slack_notification(error_msg, "graduate_totalacademic_rss")
        return {
            "statusCode": 500,
        }


def parse_date(date_str):
    """RSS 날짜 문자열을 datetime 객체로 변환합니다."""
    try:
        dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
        return dt
    except Exception as e:
        print(f"❌ [PARSE] 날짜 파싱 오류: {e}")
        return datetime.now(pytz.timezone("Asia/Seoul"))


def parse_link(raw_link):
    """RSS의 link 값을 절대 URL로 변환합니다.

    이 게시판의 RSS는 link에 전체 URL이 아닌 글 번호만 담고 있습니다.
    (예: <link>456</link> -> https://gds.kookmin.ac.kr/information/epartmentnotice/456)
    """
    link = (raw_link or "").strip()
    if not link:
        return None
    if link.startswith("http"):
        return link
    return urljoin(BASE_URL, link)


def scrape_graduate_totalacademic_rss() -> Dict[str, Any]:
    """대학원 전체학과게시판공지 RSS를 스크래핑하고 새로운 공지사항을 처리"""

    url = "https://gds.kookmin.ac.kr/information/epartmentnotice/rss"
    kst = pytz.timezone("Asia/Seoul")

    print(f"🌐 [SCRAPER] 대학원 전체학과게시판공지 RSS 스크래핑 시작 - URL: {url}")

    try:
        # 기존 공지사항 확인 (MongoDB에서)
        recent_notices = get_recent_notices("graduate_totalacademic_rss")
        recent_links = {notice.get("link") for notice in recent_notices}
        recent_titles = {notice.get("title") for notice in recent_notices}

        # RSS 피드 파싱
        feed = feedparser.parse(url)
        new_notices = []

        print(f"📊 [SCRAPER] RSS 피드 항목 수: {len(feed.entries)}")

        for entry in feed.entries[:20]:  # 최근 20개만 가져오기
            link = parse_link(entry.get("link"))
            if not link:
                print(f"⚠️ [SCRAPER] 링크가 없어 건너뜀: {entry.title[:30]}...")
                continue

            notice = {
                "title": entry.title,
                "link": link,
                "published": parse_date(entry.published).isoformat(),
                "scraper_type": "graduate_totalacademic_rss",
            }

            print(f"📝 [SCRAPER] 공지사항: {notice['title'][:30]}...")

            # 30일 이내의 데이터만 필터링
            thirty_days_ago = datetime.now(kst) - timedelta(days=30)
            published_date = parse_date(entry.published)
            if published_date >= thirty_days_ago:
                # 중복 확인
                if notice["link"] in recent_links or notice["title"] in recent_titles:
                    print(
                        f"⏭️ [SCRAPER] 중복 공지사항 건너뜀: {notice['title'][:30]}..."
                    )
                else:
                    new_notices.append(notice)
                    print(f"🆕 [SCRAPER] 새로운 공지사항: {notice['title'][:30]}...")
            else:
                print(
                    f"⏰ [SCRAPER] 30일 이전 공지사항 제외: {notice['title'][:30]}..."
                )

        print(f"📈 [SCRAPER] 새로운 공지사항 수: {len(new_notices)}")

        # 새로운 공지사항을 MongoDB에 저장
        saved_count = 0
        if new_notices:
            saved_count = save_notices_to_db(new_notices, "graduate_totalacademic_rss")
            print(f"💾 [SCRAPER] 저장 완료: {saved_count}개")

        result = {
            "success": True,
            "message": "대학원 전체학과게시판공지 RSS 스크래핑 완료",
            "total_found": len(feed.entries),
            "new_notices_count": len(new_notices),
            "saved_count": saved_count,
            "new_notices": new_notices,
        }

        print(f"🎉 [SCRAPER] 스크래핑 완료")
        return result

    except Exception as e:
        error_msg = f"스크래핑 중 오류: {str(e)}"
        print(f"❌ [SCRAPER] {error_msg}")
        send_slack_notification(error_msg, "graduate_totalacademic_rss")
        return {"success": False, "error": error_msg}
