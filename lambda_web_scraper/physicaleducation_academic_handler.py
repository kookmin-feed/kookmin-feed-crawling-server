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
    체육대학 학사공지 스크래퍼 Lambda Handler
    깔끔하고 독립적인 구현
    """

    print("🚀 [HANDLER] Lambda Handler 시작")

    try:
        # 동기 스크래퍼 실행
        result = scrape_physicaleducation_academic()

        return {
            "statusCode": 200,
        }

    except Exception as e:
        error_msg = f"Lambda Handler 실행 중 오류: {str(e)}"
        print(f"❌ [HANDLER] {error_msg}")
        send_slack_notification(error_msg, "physicaleducation_academic")
        return {
            "statusCode": 500,
        }


def scrape_physicaleducation_academic() -> Dict[str, Any]:
    """
    체육대학 학사공지를 스크래핑하고 새로운 공지사항을 처리
    """

    url = "https://sport.kookmin.ac.kr/sports/notice/notice01.do"
    kst = pytz.timezone("Asia/Seoul")

    print(f"🌐 [SCRAPER] 스크래핑 시작 - URL: {url}")

    try:
        # 웹페이지 가져오기
        soup = fetch_page(url)

        # 공지사항 목록 요소들 가져오기
        table = soup.select_one("table.board-table")
        if not table:
            print("❌ [SCRAPER] 테이블을 찾을 수 없습니다")
            return {"success": False, "error": "테이블을 찾을 수 없습니다"}

        elements = table.select("tbody tr")
        print(f"📊 [SCRAPER] 발견된 공지사항 수: {len(elements)}")

        # 기존 공지사항 확인 (MongoDB에서)
        recent_notices = get_recent_notices("physicaleducation_academic")
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
            saved_count = save_notices_to_db(new_notices, "physicaleducation_academic")
            print(f"💾 [SCRAPER] 저장 완료: {saved_count}개")

        result = {
            "success": True,
            "message": f"체육대학 학사공지 스크래핑 완료",
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
        send_slack_notification(error_msg, "physicaleducation_academic")
        return {"success": False, "error": error_msg}


def parse_notice_from_element(element, kst, base_url) -> Dict[str, Any]:
    """HTML 요소에서 체육대학 공지사항 정보를 추출"""

    try:
        # 공지사항 여부 확인
        notice_td = element.select_one("td.b-num-box.num-notice")
        is_notice = notice_td is not None and "공지" in notice_td.text.strip()

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
            link = f"https://sport.kookmin.ac.kr{relative_link}"
        else:
            link = f"https://sport.kookmin.ac.kr/{relative_link}"

        # 날짜 추출
        date_span = element.select_one("span.b-date")
        if not date_span:
            published = datetime.now(kst)
        else:
            date_text = date_span.text.strip()
            try:
                # YYYY-MM-DD 형식 (예: 2024-12-18)
                published = datetime.strptime(date_text, "%Y-%m-%d").replace(tzinfo=kst)
            except ValueError:
                try:
                    # YYYY.MM.DD 형식
                    published = datetime.strptime(date_text, "%Y.%m.%d").replace(
                        tzinfo=kst
                    )
                except ValueError:
                    try:
                        # YY.MM.DD 형식 (예: 24.08.06)
                        published = datetime.strptime(date_text, "%y.%m.%d").replace(
                            tzinfo=kst
                        )
                    except ValueError:
                        print(f"❌ [PARSE] 날짜 파싱 오류: {date_text}")
                        published = datetime.now(kst)

        # 공지사항인 경우 제목 앞에 [공지] 표시 추가
        if is_notice and not title.startswith("[공지]"):
            title = f"[공지] {title}"

        # 로깅
        if is_notice:
            print(f"🔔 [PARSE] 상단 고정 공지 파싱: {title}")
        else:
            print(f"📝 [PARSE] 일반 공지 파싱: {title}")

        result = {
            "title": title,
            "link": link,
            "published": published.isoformat(),
            "scraper_type": "physicaleducation_academic",
        }

        return result

    except Exception as e:
        print(f"❌ [PARSE] 공지사항 파싱 중 오류: {e}")
        return None
