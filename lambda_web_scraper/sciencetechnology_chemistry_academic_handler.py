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
    응용화학부 학사공지 스크래퍼 Lambda Handler
    깔끔하고 독립적인 구현
    """

    print("🚀 [HANDLER] Lambda Handler 시작")

    try:
        # 동기 스크래퍼 실행
        result = scrape_sciencetechnology_chemistry_academic()

        return {
            "statusCode": 200,
        }

    except Exception as e:
        error_msg = f"Lambda Handler 실행 중 오류: {str(e)}"
        print(f"❌ [HANDLER] {error_msg}")
        send_slack_notification(error_msg, "sciencetechnology_chemistry_academic")
        return {
            "statusCode": 500,
        }


def scrape_sciencetechnology_chemistry_academic() -> Dict[str, Any]:
    """
    응용화학부 학사공지를 스크래핑하고 새로운 공지사항을 처리
    """

    url = "http://chem.kookmin.ac.kr/sub6/menu1.php"
    kst = pytz.timezone("Asia/Seoul")

    print(f"🌐 [SCRAPER] 스크래핑 시작 - URL: {url}")

    try:
        # 웹페이지 가져오기
        soup = fetch_page(url)

        # 공지사항 목록 요소들 가져오기
        table = soup.select_one("div#ezsBBS table")
        if not table:
            print("❌ [SCRAPER] 테이블을 찾을 수 없습니다")
            return {"success": False, "error": "테이블을 찾을 수 없습니다"}

        elements = table.select("tr")
        # 헤더 행을 제외한 모든 행
        elements = elements[1:] if len(elements) > 1 else []
        print(f"📊 [SCRAPER] 발견된 공지사항 수: {len(elements)}")

        # 기존 공지사항 확인 (MongoDB에서)
        recent_notices = get_recent_notices("sciencetechnology_chemistry_academic")
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
            saved_count = save_notices_to_db(
                new_notices, "sciencetechnology_chemistry_academic"
            )
            print(f"💾 [SCRAPER] 저장 완료: {saved_count}개")

        result = {
            "success": True,
            "message": f"응용화학부 학사공지 스크래핑 완료",
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
        send_slack_notification(error_msg, "sciencetechnology_chemistry_academic")
        return {"success": False, "error": error_msg}


def parse_notice_from_element(element, kst, base_url) -> Dict[str, Any]:
    """HTML 요소에서 응용화학부 공지사항 정보를 추출"""

    try:
        # 제목과 링크 추출
        title_link = element.select_one("td ul li a.Board")
        if not title_link:
            return None

        title = title_link.text.strip()
        relative_link = title_link.get("href", "")

        # 상대 경로를 절대 경로로 변환
        if relative_link.startswith("/"):
            link = f"http://chem.kookmin.ac.kr{relative_link}"
        else:
            link = f"http://chem.kookmin.ac.kr/sub6/{relative_link}"

        # 날짜 추출
        date_cells = element.select("td.txtc.txtN")
        if len(date_cells) >= 3:  # 번호, 날짜, 조회수 순서로 있을 것으로 예상
            date_str = date_cells[1].text.strip()
            try:
                published = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=kst)
            except ValueError:
                try:
                    published = datetime.strptime(date_str, "%Y.%m.%d").replace(
                        tzinfo=kst
                    )
                except ValueError:
                    print(f"❌ [PARSE] 날짜 파싱 오류: {date_str}")
                    published = datetime.now(kst)
        else:
            print("⚠️ [PARSE] 날짜 요소를 찾을 수 없음")
            published = datetime.now(kst)

        result = {
            "title": title,
            "link": link,
            "published": published.isoformat(),
            "scraper_type": "sciencetechnology_chemistry_academic",
        }

        return result

    except Exception as e:
        print(f"❌ [PARSE] 공지사항 파싱 중 오류: {e}")
        return None
