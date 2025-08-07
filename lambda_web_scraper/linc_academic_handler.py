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
    LINC 3.0 사업단 학사공지 스크래퍼 Lambda Handler
    깔끔하고 독립적인 구현
    """
    print("🚀 [HANDLER] Lambda Handler 시작")
    try:
        # 동기 스크래퍼 실행
        scrape_linc_academic()
        return {
            "statusCode": 200,
        }
    except Exception as e:
        error_msg = f"Lambda Handler 실행 중 오류: {str(e)}"
        print(f"❌ [HANDLER] {error_msg}")
        send_slack_notification(error_msg, "linc_academic")
        return {
            "statusCode": 500,
        }

def scrape_linc_academic() -> None:
    """
    LINC 3.0 사업단 학사공지를 스크래핑하고 새로운 공지사항을 처리
    """
    url = "https://linc.kookmin.ac.kr/main/menu?gc=605XOAS"
    kst = pytz.timezone("Asia/Seoul")
    print(f"🌐 [SCRAPER] 스크래핑 시작 - URL: {url}")
    try:
        # 웹페이지 가져오기
        soup = fetch_page(url)
        # 공지사항 목록 요소들 가져오기
        elements = soup.select(".board_list .content_wrap li")
        print(f"📊 [SCRAPER] 발견된 공지사항 수: {len(elements)}")
        # 기존 공지사항 확인 (MongoDB에서)
        recent_notices = get_recent_notices("linc_academic")
        recent_links = {notice.get("link") for notice in recent_notices}
        recent_titles = {notice.get("title") for notice in recent_notices}
        # 새로운 공지사항 파싱
        new_notices = []
        for element in elements:
            notice = parse_notice_from_element(element, kst, url)
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
                        print(f"🆕 [SCRAPER] 새로운 공지사항: {notice['title'][:30]}...")
                else:
                    print(f"⏰ [SCRAPER] 30일 이전 공지사항 제외: {notice['title'][:30]}...")
        print(f"📈 [SCRAPER] 새로운 공지사항 수: {len(new_notices)}")
        # 새로운 공지사항을 MongoDB에 저장
        saved_count = 0
        if new_notices:
            saved_count = save_notices_to_db(new_notices, "linc_academic")
            print(f"💾 [SCRAPER] 저장 완료: {saved_count}개")
        print(f"🎉 [SCRAPER] 스크래핑 완료")
    except Exception as e:
        error_msg = f"스크래핑 중 오류: {str(e)}"
        print(f"❌ [SCRAPER] {error_msg}")
        send_slack_notification(error_msg, "linc_academic")

def parse_notice_from_element(element, kst, base_url) -> Dict[str, Any]:
    """HTML 요소에서 LINC 3.0 사업단 학사공지 정보를 추출"""
    try:
        # 공지사항 여부 확인
        is_notice = element.select_one(".icon_notice") is not None
        # 제목과 링크 추출
        title_element = element.select_one("a")
        if not title_element:
            return None
        title = title_element.select_one(".tit0").get_text(strip=True)
        # 상대 경로 추출 및 URL 생성
        relative_link = title_element.get("href", "")
        if relative_link.startswith("https://"):
            link = relative_link
        else:
            link = (
                f"https://linc.kookmin.ac.kr/main/menu{relative_link[1:]}"
                if relative_link.startswith("/")
                else f"https://linc.kookmin.ac.kr/main/menu{relative_link}"
            )
        # 날짜 추출
        date_str = element.select_one(".date").get_text(strip=True)
        try:
            published = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=kst)
        except ValueError:
            published = datetime.strptime(date_str, "%Y.%m.%d").replace(tzinfo=kst)
        result = {
            "title": title,
            "link": link,
            "published": published.isoformat(),
            "scraper_type": "linc_academic",
        }
        return result
    except Exception as e:
        print(f"❌ [PARSE] 공지사항 파싱 중 오류: {e}")
        return None
