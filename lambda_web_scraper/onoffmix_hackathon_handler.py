import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple, List
import pytz

from common_utils import (
    get_recent_notices,
    save_notices_to_db,
    send_slack_notification,
    setup_playwright_browser,
    get_recent_title_link_sets,
    is_within_days,
)


def parse_deadline_text(deadline_text: str, kst: pytz.timezone) -> datetime:
    """
    온오프믹스 리스트의 "마감 X전" 정보를 기반으로 마감 예상일을 계산.
    지원 단위: 시간, 일, 주, 달
    """
    try:
        text = deadline_text.strip()
        number_match = re.search(r"(\d+)", text)
        if not number_match:
            return datetime.now(kst)

        amount = int(number_match.group(1))
        if "시간" in text:
            return datetime.now(kst) + timedelta(hours=amount)
        if "일" in text:
            return datetime.now(kst) + timedelta(days=amount)
        if "주" in text:
            return datetime.now(kst) + timedelta(weeks=amount)
        if "달" in text or "개월" in text:
            return datetime.now(kst) + timedelta(days=30 * amount)

        return datetime.now(kst)
    except Exception as e:
        print(f"⚠️ [PARSER] 마감일 파싱 실패: {deadline_text}, 오류: {e}")
        return datetime.now(kst)


def _setup_browser() -> Tuple[Any, Any, Any]:
    return setup_playwright_browser()


def _navigate_to_main_page(page: Any, url: str) -> None:
    page.goto(url, timeout=30000)
    page.wait_for_selector("ul.event_lists", timeout=10000)
    page.wait_for_timeout(1500)


def _get_event_items(page: Any) -> List[Any]:
    items = page.query_selector_all("ul.event_lists > li")
    items = items[:20]
    print(f"📊 [SCRAPER] 발견된 이벤트 수: {len(items)} (최신 20개만 처리)")
    return items


def _is_ad_item(item: Any) -> bool:
    """
    광고 공고는 `article.event_area.event_main.adv_list` 클래스를 가짐.
    해당 항목은 스크래핑 대상에서 제외한다.
    """
    try:
        return item.query_selector("article.event_area.event_main.adv_list") is not None
    except Exception:
        return False


def _is_ended(item: Any) -> bool:
    # 활성 상태가 명시된 경우 우선적으로 종료 아님 처리
    try:
        if item.query_selector(".event_state_area .before_closing"):
            return False
    except Exception:
        pass

    end_txt = item.query_selector("p.end_txt")
    if not end_txt:
        return False

    # 요소의 실제 가시성 체크 (숨김 상태면 종료로 보지 않음)
    try:
        is_visible = end_txt.evaluate(
            """
            el => {
                const style = getComputedStyle(el);
                const visible = style.visibility !== 'hidden' && style.display !== 'none';
                const inFlow = !!(el.offsetParent || el.getClientRects().length);
                return visible && inFlow;
            }
            """
        )
    except Exception:
        is_visible = True

    if not is_visible:
        return False

    try:
        txt = end_txt.text_content().strip()
    except Exception:
        txt = ""

    return ("종료된 이벤트입니다" in txt) or ("종료" in txt)


def _extract_title_from_item(item: Any, index: int) -> Optional[Tuple[str, Any]]:
    article = item.query_selector("article.event_area.event_main")
    if not article:
        print(f"⚠️ [SCRAPER] 항목 {index+1}에서 article 요소 없음")
        return None
    title_el = article.query_selector("h5.title")
    if not title_el:
        print(f"⚠️ [SCRAPER] 항목 {index+1}에서 제목 요소 없음")
        return None
    title = title_el.evaluate("el => el.textContent").strip()
    print(f"📰 [SCRAPER] 제목: '{title}'")
    return title, article


def _extract_link_from_item(article: Any, index: int) -> Optional[str]:
    link_el = article.query_selector("a")
    if not link_el:
        print(f"⚠️ [SCRAPER] 항목 {index+1} 링크 요소 없음")
        return None
    href = link_el.get_attribute("href")
    if not href:
        return None
    if href.startswith("/"):
        href = f"https://onoffmix.com{href}"
    print(f"🔗 [SCRAPER] 링크: '{href}'")
    return href


def _extract_deadline_from_item(article: Any, index: int) -> Optional[str]:
    day_el = article.query_selector(".event_state_area .before_closing .day")
    if day_el:
        day_text = day_el.text_content().strip()
        print(f"📅 [SCRAPER] 마감까지: '{day_text}'")
        return day_text
    # 대체: 리스트의 날짜 텍스트 (가공은 어렵기에 로그만 남김)
    date_el = article.query_selector(".list_date_place .date, .event_info .date")
    if date_el:
        alt_text = date_el.text_content().strip()
        print(f"📅 [SCRAPER] 대체 날짜 정보: '{alt_text}'")
    return None


def _create_notice_data(
    title: str, link: str, published_date: datetime
) -> Dict[str, Any]:
    return {
        "title": title,
        "link": link,
        "published": published_date.isoformat(),
        "scraper_type": "onoffmix_hackathon",
    }


def _process_single_event(
    item: Any, index: int, recent_titles: set, recent_links: set, kst: pytz.timezone
) -> Optional[Dict[str, Any]]:
    try:
        print(f"🔍 [SCRAPER] 이벤트 {index+1} 처리 시작")

        if _is_ad_item(item):
            print(f"🪧 [SCRAPER] 광고 항목 (스킵): index={index+1}")
            return None

        if _is_ended(item):
            print(f"⛔ [SCRAPER] 종료된 이벤트 (스킵): index={index+1}")
            return None

        title_info = _extract_title_from_item(item, index)
        if not title_info:
            return None
        title, article = title_info

        if title in recent_titles:
            print(f"♻️ [SCRAPER] 기존 제목 (스킵): {title[:30]}...")
            return None

        link = _extract_link_from_item(article, index)
        if not link:
            return None

        if link in recent_links:
            print(f"♻️ [SCRAPER] 기존 링크 (스킵): {link}")
            return None

        deadline_text = _extract_deadline_from_item(article, index)
        published = (
            parse_deadline_text(deadline_text, kst)
            if deadline_text
            else datetime.now(kst)
        )

        notice = _create_notice_data(title, link, published)

        if is_within_days(notice["published"], 30, kst):
            print(f"🆕 [SCRAPER] 새로운 이벤트 추가: {title[:30]}...")
            return notice
        else:
            print(f"⏰ [SCRAPER] 30일 이전 데이터 제외: {title[:30]}...")
            return None
    except Exception as e:
        print(f"⚠️ [SCRAPER] 이벤트 {index+1} 처리 중 오류: {e}")
        return None


def scrape_onoffmix_hackathon() -> Dict[str, Any]:
    url = "https://onoffmix.com/event/main?s=%ED%95%B4%EC%BB%A4%ED%86%A4"
    kst = pytz.timezone("Asia/Seoul")
    print(f"🌐 [SCRAPER] 스크래핑 시작 - URL: {url}")

    try:
        p, browser, page = _setup_browser()
        new_notices: List[Dict[str, Any]] = []

        try:
            _navigate_to_main_page(page, url)
            items = _get_event_items(page)

            if not items:
                print("❌ [SCRAPER] 이벤트 항목을 찾을 수 없음")
                return {"success": False, "error": "이벤트 항목을 찾을 수 없음"}

            _, _, recent = get_recent_title_link_sets("onoffmix_hackathon")
            recent_links = {n.get("link") for n in recent}
            recent_titles = {n.get("title") for n in recent}
            print(f"📋 [DB] 기존 온오프믹스 해커톤 수: {len(recent)}")

            for i in range(len(items)):
                current_items = page.query_selector_all("ul.event_lists > li")
                if i >= len(current_items):
                    print(f"⚠️ [SCRAPER] 이벤트 {i+1} 인덱스 초과")
                    continue
                item = current_items[i]
                notice = _process_single_event(
                    item, i, recent_titles, recent_links, kst
                )
                if notice:
                    new_notices.append(notice)
        finally:
            browser.close()
            p.stop()

        print(f"📈 [SCRAPER] 새로운 온오프믹스 해커톤 수: {len(new_notices)}")
        saved_count = 0
        if new_notices:
            saved_count = save_notices_to_db(new_notices, "onoffmix_hackathon")
            print(f"💾 [SCRAPER] 저장 완료: {saved_count}개")

        result = {
            "success": True,
            "message": "온오프믹스 해커톤 스크래핑 완료",
            "total_found": len(items),
            "new_notices_count": len(new_notices),
            "saved_count": saved_count,
            "new_notices": new_notices,
        }
        print("🎉 [SCRAPER] 스크래핑 완료")
        return result
    except Exception as e:
        error_msg = f"스크래핑 중 오류: {str(e)}"
        print(f"❌ [SCRAPER] {error_msg}")
        send_slack_notification(error_msg, "onoffmix_hackathon")
        return {"success": False, "error": error_msg}


def handler(event, context):
    print("🚀 [HANDLER] Lambda Handler 시작 (onoffmix_hackathon)")
    try:
        scrape_onoffmix_hackathon()
        return {"statusCode": 200}
    except Exception as e:
        error_msg = f"Lambda Handler 실행 중 오류: {str(e)}"
        print(f"❌ [HANDLER] {error_msg}")
        send_slack_notification(error_msg, "onoffmix_hackathon")
        return {"statusCode": 500}
