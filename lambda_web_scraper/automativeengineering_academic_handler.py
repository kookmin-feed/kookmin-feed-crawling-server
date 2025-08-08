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
    자동차융합대학 학사공지 스크래퍼 Lambda Handler
    """
    print("🚀 [HANDLER] Lambda Handler 시작")
    try:
        result = scrape_automativeengineering_academic()
        return {
            "statusCode": 200,
        }
    except Exception as e:
        error_msg = f"Lambda Handler 실행 중 오류: {str(e)}"
        print(f"❌ [HANDLER] {error_msg}")
        send_slack_notification(error_msg, "automativeengineering_academic")
        return {
            "statusCode": 500,
        }


def scrape_automativeengineering_academic() -> Dict[str, Any]:
    """
    자동차융합대학 학사공지를 스크래핑하고 새로운 공지사항을 처리
    """
    url = "https://auto.kookmin.ac.kr/board/notice/?&pn=0"
    kst = pytz.timezone("Asia/Seoul")
    print(f"🌐 [SCRAPER] 스크래핑 시작 - URL: {url}")
    try:
        soup = fetch_page(url)
        # 일반 공지: 메인 리스트(페이지네이션 제외)
        elements_main = soup.select("div.list-type01.list-l > ul > li")
        # 상단 고정 공지: aside 리스트
        elements_aside = soup.select("div.aside-list-area ul li.aside-list")
        elements = elements_main + elements_aside
        print(
            f"📊 [SCRAPER] 발견된 공지사항 수 | 일반: {len(elements_main)}, 상단고정: {len(elements_aside)}, 합계: {len(elements)}"
        )
        recent_notices = get_recent_notices("automativeengineering_academic")
        recent_links = {notice.get("link") for notice in recent_notices}
        recent_titles = {notice.get("title") for notice in recent_notices}
        new_notices = []
        for element in elements:
            notice = parse_notice_from_element(element, kst)
            if notice:
                thirty_days_ago = datetime.now(kst) - timedelta(days=30)
                published_date = datetime.fromisoformat(
                    notice["published"].replace("Z", "+00:00")
                )
                if published_date >= thirty_days_ago:
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
        saved_count = 0
        if new_notices:
            saved_count = save_notices_to_db(
                new_notices, "automativeengineering_academic"
            )
            print(f"💾 [SCRAPER] 저장 완료: {saved_count}개")
        result = {
            "success": True,
            "message": f"자동차융합대학 학사공지 스크래핑 완료",
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
        send_slack_notification(error_msg, "automativeengineering_academic")
        return {"success": False, "error": error_msg}


def parse_notice_from_element(element, kst) -> Dict[str, Any]:
    """HTML 요소에서 학사공지 정보를 추출"""
    try:
        # 공통: 링크 태그 확인
        link_tag = element.select_one("a")
        if not link_tag:
            return None

        href_value = link_tag.get("href", "").strip()
        if not href_value:
            return None

        # 1) 일반 공지: list-type01 list-l 구조
        #    - strong.list01-tit, span.list01-date
        title_tag_main = element.select_one("strong.list01-tit")
        date_tag_main = element.select_one("span.list01-date")
        if title_tag_main and date_tag_main:
            title = title_tag_main.get_text(strip=True)
            date_str = date_tag_main.get_text(strip=True)
            published = datetime.strptime(date_str, "%Y.%m.%d").replace(tzinfo=kst)
            full_url = f"https://auto.kookmin.ac.kr/board/notice/{href_value}"
            return {
                "title": title,
                "link": full_url,
                "published": published.isoformat(),
                "scraper_type": "automativeengineering_academic",
            }

        # 2) 상단 고정 공지: aside-list-area 구조
        #    - a 하위의 span(날짜), strong(제목)
        title_tag_aside = link_tag.select_one("strong")
        date_tag_aside = link_tag.select_one("span")
        if title_tag_aside and date_tag_aside:
            title = title_tag_aside.get_text(strip=True)
            date_str = date_tag_aside.get_text(strip=True)
            published = datetime.strptime(date_str, "%Y.%m.%d").replace(tzinfo=kst)
            full_url = f"https://auto.kookmin.ac.kr/board/notice/{href_value}"
            return {
                "title": title,
                "link": full_url,
                "published": published.isoformat(),
                "scraper_type": "automativeengineering_academic",
            }

        # 인식되지 않는 구조
        return None
    except Exception as e:
        print(f"❌ [PARSE] 공지사항 파싱 중 오류: {e}")
        return None
