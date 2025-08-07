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
    도자공예학과 학사공지 스크래퍼 Lambda Handler
    깔끔하고 독립적인 구현
    """
    print("🚀 [HANDLER] Lambda Handler 시작")
    try:
        # 동기 스크래퍼 실행
        result = scrape_design_ceramics_academic()
        return {
            "statusCode": 200,
        }
    except Exception as e:
        error_msg = f"Lambda Handler 실행 중 오류: {str(e)}"
        print(f"❌ [HANDLER] {error_msg}")
        send_slack_notification(error_msg, "design_ceramics_academic")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": error_msg}, ensure_ascii=False),
        }

def scrape_design_ceramics_academic() -> Dict[str, Any]:
    """
    도자공예학과 학사공지를 스크래핑하고 새로운 공지사항을 처리
    """
    url = "https://kmuceramics.com/news/"
    kst = pytz.timezone("Asia/Seoul")
    print(f"🌐 [SCRAPER] 스크래핑 시작 - URL: {url}")
    try:
        # 웹페이지 가져오기
        soup = fetch_page(url)
        # 공지사항 목록 요소들 가져오기
        table = soup.select_one("div.kboard-list table")
        if not table:
            print("❌ [SCRAPER] 테이블을 찾을 수 없습니다")
            return {"success": False, "error": "테이블을 찾을 수 없습니다"}
        
        elements = table.select("tbody tr")
        print(f"📊 [SCRAPER] 발견된 공지사항 수: {len(elements)}")
        # 기존 공지사항 확인 (MongoDB에서)
        recent_notices = get_recent_notices("design_ceramics_academic")
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
            saved_count = save_notices_to_db(new_notices, "design_ceramics_academic")
            print(f"💾 [SCRAPER] 저장 완료: {saved_count}개")
        result = {
            "success": True,
            "message": f"도자공예학과 학사공지 스크래핑 완료",
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
        send_slack_notification(error_msg, "design_ceramics_academic")
        return {"success": False, "error": error_msg}

def parse_notice_from_element(element, kst, base_url) -> Dict[str, Any]:
    """HTML 요소에서 도자공예학과 학사공지 정보를 추출"""
    try:
        # 제목과 링크 추출
        title_td = element.select_one("td.kboard-list-title")
        if not title_td:
            return None

        a_tag = title_td.select_one("a")
        if not a_tag:
            return None

        # 카테고리가 있으면 제목에 포함
        category_span = title_td.select_one("span.category1")
        category_text = ""
        if category_span:
            category_text = category_span.text.strip()

        # 제목 텍스트 추출 (카테고리를 제외한 실제 제목)
        title_div = title_td.select_one("div.kboard-default-cut-strings")
        if title_div:
            # 카테고리 부분을 제외한 텍스트 추출
            title = title_div.get_text(strip=True)
            if category_span:
                title = title.replace(category_text, "").strip()
        else:
            title = a_tag.get_text(strip=True)

        # 카테고리가 제목 앞에 있으면 그대로 사용
        if category_text:
            title = f"{category_text} {title}"

        # 링크 추출
        relative_link = a_tag.get("href", "")
        if relative_link.startswith("/"):
            link = f"https://kmuceramics.com{relative_link}"
        else:
            link = relative_link

        # 날짜 추출
        date_td = element.select_one("td.kboard-list-date")
        if not date_td:
            published = datetime.now(kst)
        else:
            date_str = date_td.text.strip()
            try:
                published = datetime.strptime(date_str, "%Y.%m.%d").replace(tzinfo=kst)
            except ValueError:
                try:
                    published = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=kst)
                except ValueError:
                    try:
                        # 'YY.MM.DD' 형식 추가
                        published = datetime.strptime(date_str, "%y.%m.%d").replace(tzinfo=kst)
                    except ValueError:
                        print(f"❌ [PARSE] 날짜 파싱 오류: {date_str}")
                        published = datetime.now(kst)

        result = {
            "title": title,
            "link": link,
            "published": published.isoformat(),
            "scraper_type": "design_ceramics_academic",
        }
        return result
    except Exception as e:
        print(f"❌ [PARSE] 공지사항 파싱 중 오류: {e}")
        return None
