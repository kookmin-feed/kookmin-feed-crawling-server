import json

from datetime import datetime, timedelta
import pytz
import re
from typing import Dict, Any
from common_utils import (
    fetch_page,
    get_recent_notices,
    save_notices_to_db,
    send_slack_notification,
)


def handler(event, context):
    """
    대학 공모행사공지 스크래퍼 Lambda Handler
    깔끔하고 독립적인 구현
    """

    print("🚀 [HANDLER] Lambda Handler 시작")

    try:
        # 동기 스크래퍼 실행
        result = scrape_university_contestevent()

        return {
            "statusCode": 200,
        }

    except Exception as e:
        error_msg = f"Lambda Handler 실행 중 오류: {str(e)}"
        print(f"❌ [HANDLER] {error_msg}")
        send_slack_notification(error_msg, "university_contestevent")
        return {
            "statusCode": 500,
        }


def scrape_university_contestevent() -> Dict[str, Any]:
    """
    대학 공모행사공지를 스크래핑하고 새로운 공지사항을 처리
    """

    url = "https://www.kookmin.ac.kr/user/kmuNews/notice/9/index.do"
    kst = pytz.timezone("Asia/Seoul")

    print(f"🌐 [SCRAPER] 스크래핑 시작 - URL: {url}")

    try:
        # 웹페이지 가져오기
        soup = fetch_page(url)

        # 공지사항 목록 요소들 가져오기
        elements = soup.select("div.board_list > ul > li")
        print(f"📊 [SCRAPER] 발견된 공지사항 수: {len(elements)}")

        # 기존 공지사항 확인 (MongoDB에서)
        recent_notices = get_recent_notices("university_contestevent")
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
            saved_count = save_notices_to_db(new_notices, "university_contestevent")
            print(f"💾 [SCRAPER] 저장 완료: {saved_count}개")

        result = {
            "success": True,
            "message": f"대학 공모행사공지 스크래핑 완료",
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
        send_slack_notification(error_msg, "university_contestevent")
        return {"success": False, "error": error_msg}


def parse_notice_from_element(element, kst) -> Dict[str, Any]:
    """HTML 요소에서 공모행사공지 정보를 추출"""

    try:
        base_url = "https://www.kookmin.ac.kr"

        # 공지사항 여부 확인
        is_notice = "notice" in element.get("class", [])

        # 제목과 링크 추출 - 공지사항과 일반 게시물의 구조가 다름
        a_tag = element.select_one("a")
        if not a_tag:
            return None

        relative_link = a_tag.get("href", "")
        # 상대 경로를 절대 경로로 변환
        if relative_link.startswith("/"):
            link = f"{base_url}{relative_link}"
        else:
            link = relative_link

        # 공지사항과 일반 게시물의 제목 추출 방식이 다름
        if is_notice:
            # 공지사항은 p.title이 a 태그 바로 아래에 있음
            title_element = a_tag.select_one("p.title")
        else:
            # 일반 게시물은 board_txt 클래스 안에 p.title이 있음
            title_element = a_tag.select_one("div.board_txt p.title")

        if not title_element:
            return None

        title = title_element.get_text(strip=True)

        # 날짜 추출 - 일반 게시물과 공지사항 처리 방식이 다름
        if is_notice:
            # 공지사항은 상세 페이지에서 날짜를 가져와야 함
            published = get_date_from_detail_page(link, kst)
        else:
            # 일반 게시물은 목록에서 날짜 추출
            date_element = element.select_one("div.board_etc span:first-child")
            if not date_element:
                # 날짜를 찾을 수 없는 경우 상세 페이지에서 가져옴
                published = get_date_from_detail_page(link, kst)
            else:
                date_str = date_element.get_text(strip=True)
                try:
                    # YYYY.MM.DD 형식
                    published = datetime.strptime(date_str, "%Y.%m.%d").replace(
                        tzinfo=kst
                    )
                except ValueError:
                    try:
                        # YYYY-MM-DD 형식
                        published = datetime.strptime(date_str, "%Y-%m-%d").replace(
                            tzinfo=kst
                        )
                    except ValueError:
                        # 날짜 형식이 다른 경우 상세 페이지에서 가져옴
                        published = get_date_from_detail_page(link, kst)

        # 공지사항인 경우 제목 앞에 [공지] 표시 추가
        if is_notice and not title.startswith("[공지]"):
            title = f"[공지] {title}"

        result = {
            "title": title,
            "link": link,
            "published": published.isoformat(),
            "scraper_type": "university_contestevent",
        }

        return result

    except Exception as e:
        print(f"❌ [PARSE] 공지사항 파싱 중 오류: {e}")
        return None


def get_date_from_detail_page(url: str, kst) -> datetime:
    """상세 페이지에서 날짜 정보를 추출합니다."""
    try:
        soup = fetch_page(url)

        # 상세 페이지에서 날짜 요소 찾기 - view_top > board_etc > 작성일 span
        date_element = soup.select_one("div.view_top div.board_etc span:first-child")
        if not date_element:
            print(f"⚠️ [DETAIL] 상세 페이지에서 날짜 요소를 찾을 수 없음: {url}")
            return datetime.now(kst)

        date_str = date_element.get_text(strip=True)
        # "작성일 2025.03.07" 형식에서 날짜만 추출
        date_match = re.search(r"작성일\s+(\d{4}[-\.]\d{1,2}[-\.]\d{1,2})", date_str)
        if date_match:
            date_str = date_match.group(1)
        else:
            # 다른 형식일 수 있으므로 일반적인 날짜 패턴 검색
            date_match = re.search(r"(\d{4}[-\.]\d{1,2}[-\.]\d{1,2})", date_str)
            if date_match:
                date_str = date_match.group(1)
            else:
                print(f"⚠️ [DETAIL] 날짜 형식을 인식할 수 없음: {date_str}")
                return datetime.now(kst)

        try:
            # YYYY.MM.DD 형식
            if "." in date_str:
                return datetime.strptime(date_str, "%Y.%m.%d").replace(tzinfo=kst)
            # YYYY-MM-DD 형식
            else:
                return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=kst)
        except ValueError as e:
            print(f"❌ [DETAIL] 날짜 파싱 오류: {date_str}, {e}")
            return datetime.now(kst)
    except Exception as e:
        print(f"❌ [DETAIL] 상세 페이지 요청 중 오류: {e}")
        return datetime.now(kst)
