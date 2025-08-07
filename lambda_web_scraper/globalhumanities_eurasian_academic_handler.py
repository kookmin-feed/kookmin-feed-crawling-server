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
    러시아유라시아학과 학사공지 스크래퍼 Lambda Handler
    깔끔하고 독립적인 구현
    """
    print("🚀 [HANDLER] Lambda Handler 시작")
    try:
        # 동기 스크래퍼 실행
        scrape_globalhumanities_eurasian_academic()
        return {
            "statusCode": 200,
        }
    except Exception as e:
        error_msg = f"Lambda Handler 실행 중 오류: {str(e)}"
        print(f"❌ [HANDLER] {error_msg}")
        send_slack_notification(error_msg, "globalhumanities_eurasian_academic")
        return {
            "statusCode": 500,
        }

def scrape_globalhumanities_eurasian_academic() -> None:
    """
    러시아유라시아학과 학사공지를 스크래핑하고 새로운 공지사항을 처리
    """
    url = "https://cms.kookmin.ac.kr/Russian-EurasianStudies/community/department-notice.do"
    kst = pytz.timezone("Asia/Seoul")
    print(f"🌐 [SCRAPER] 스크래핑 시작 - URL: {url}")
    try:
        # 웹페이지 가져오기
        soup = fetch_page(url)
        # 공지사항 목록 요소들 가져오기
        elements = []
        # 상단 고정 공지 가져오기
        top_notices = soup.select("tr.b-top-box")
        if top_notices:
            elements.extend(top_notices)
        # 일반 공지 가져오기
        normal_notices = soup.select("table.board-table > tbody > tr:not(.b-top-box)")
        if normal_notices:
            elements.extend(normal_notices)
        print(f"📊 [SCRAPER] 발견된 공지사항 수: {len(elements)}")
        # 기존 공지사항 확인 (MongoDB에서)
        recent_notices = get_recent_notices("globalhumanities_eurasian_academic")
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
            saved_count = save_notices_to_db(new_notices, "globalhumanities_eurasian_academic")
            print(f"💾 [SCRAPER] 저장 완료: {saved_count}개")
        print(f"🎉 [SCRAPER] 스크래핑 완료")
    except Exception as e:
        error_msg = f"스크래핑 중 오류: {str(e)}"
        print(f"❌ [SCRAPER] {error_msg}")
        send_slack_notification(error_msg, "globalhumanities_eurasian_academic")

def parse_notice_from_element(element, kst, base_url) -> Dict[str, Any]:
    """HTML 요소에서 러시아유라시아학과 학사공지 정보를 추출"""
    try:
        # 고정 공지 여부 확인
        is_notice = "b-top-box" in element.get("class", [])
        # 일반 공지에서 공지 표시 확인
        if not is_notice:
            notice_td = element.select_one("td.b-num-box.num-notice")
            is_notice = notice_td is not None
        # 제목과 링크 추출
        title_td = element.select_one("td.b-td-left")
        if not title_td:
            return None
        title_box = title_td.select_one("div.b-title-box")
        if not title_box:
            return None
        a_tag = title_box.select_one("a")
        if not a_tag:
            return None
        # title 속성에서 제목 추출 (자세히 보기 텍스트 제거)
        title_attr = a_tag.get("title", "")
        if title_attr:
            title = title_attr.replace(" 자세히 보기", "").strip()
        else:
            # title 속성이 없으면 텍스트 콘텐츠 사용
            title = a_tag.text.strip()
        relative_link = a_tag.get("href", "")
        # URL 파라미터 형식 확인 및 절대 경로 생성
        if relative_link.startswith("?"):
            link = f"{base_url}{relative_link}"
        elif relative_link.startswith("/"):
            link = f"https://cms.kookmin.ac.kr{relative_link}"
        else:
            link = f"https://cms.kookmin.ac.kr/{relative_link}"
        # 날짜 추출 - b-date 클래스 내의 텍스트 사용
        date_span = element.select_one("span.b-date")
        if not date_span:
            # 테이블의 날짜 셀에서 시도
            date_td = element.select_one("td:nth-child(4)")
            if date_td and date_td.text.strip():
                date_str = date_td.text.strip()
            else:
                published = datetime.now(kst)
        else:
            date_str = date_span.text.strip()
        try:
            # YYYY-MM-DD 형식
            published = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=kst)
        except ValueError:
            try:
                # YYYY.MM.DD 형식
                published = datetime.strptime(date_str, "%Y.%m.%d").replace(tzinfo=kst)
            except ValueError:
                try:
                    # YY.MM.DD 형식
                    published = datetime.strptime(date_str, "%y.%m.%d").replace(tzinfo=kst)
                except ValueError:
                    print(f"❌ [PARSE] 날짜 파싱 오류: {date_str}")
                    published = datetime.now(kst)
        # 공지사항인 경우 제목 앞에 [공지] 표시 추가
        if is_notice and not title.startswith("[공지]"):
            title = f"[공지] {title}"
        result = {
            "title": title,
            "link": link,
            "published": published.isoformat(),
            "scraper_type": "globalhumanities_eurasian_academic",
        }
        return result
    except Exception as e:
        print(f"❌ [PARSE] 공지사항 파싱 중 오류: {e}")
        return None
