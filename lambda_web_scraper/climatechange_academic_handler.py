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
    기후변화대응사업단 학사공지 스크래퍼 Lambda Handler
    깔끔하고 독립적인 구현
    """

    print("🚀 [HANDLER] Lambda Handler 시작")

    try:
        # 동기 스크래퍼 실행
        result = scrape_climatechange_academic()

        return {
            "statusCode": 200,
        }

    except Exception as e:
        error_msg = f"Lambda Handler 실행 중 오류: {str(e)}"
        print(f"❌ [HANDLER] {error_msg}")
        send_slack_notification(error_msg, "climatechange_academic")
        return {
            "statusCode": 500,
        }


def scrape_climatechange_academic() -> Dict[str, Any]:
    """
    기후변화대응사업단 학사공지를 스크래핑하고 새로운 공지사항을 처리
    """

    url = "https://cms.kookmin.ac.kr/climatechange/community/notice.do"
    kst = pytz.timezone("Asia/Seoul")

    print(f"🌐 [SCRAPER] 스크래핑 시작 - URL: {url}")

    try:
        # 웹페이지 가져오기
        soup = fetch_page(url)

        # 공지사항 목록 요소들 가져오기 (테이블 행 선택)
        elements = soup.select("table.board-table tbody tr")
        print(f"📊 [SCRAPER] 발견된 공지사항 수: {len(elements)}")

        # 기존 공지사항 확인 (MongoDB에서)
        recent_notices = get_recent_notices("climatechange_academic")
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
            saved_count = save_notices_to_db(new_notices, "climatechange_academic")
            print(f"💾 [SCRAPER] 저장 완료: {saved_count}개")

        result = {
            "success": True,
            "message": f"기후변화대응사업단 학사공지 스크래핑 완료",
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
        send_slack_notification(error_msg, "climatechange_academic")
        return {"success": False, "error": error_msg}


def parse_notice_from_element(row, kst) -> Dict[str, Any]:
    """HTML 요소에서 기후변화대응사업단 학사공지 정보를 추출"""

    try:
        # hidden input 요소들은 건너뜀
        if row.find("input", {"type": "hidden"}):
            return None

        # 제목과 링크 추출
        title_tag = row.select_one(".b-title-box a")
        if not title_tag:
            return None

        title = title_tag.text.strip()
        link = title_tag.get("href")

        # 상대 링크를 절대 링크로 변환
        if link and not link.startswith("http"):
            link = f"https://cms.kookmin.ac.kr/climatechange/community/notice.do{link}"

        # 날짜 추출 (등록일 컬럼에서)
        date_cells = row.select("td")
        if len(date_cells) < 5:  # 번호, 제목, 파일, 작성자, 등록일, 조회수
            return None

        date_str = date_cells[4].text.strip()  # 5번째 컬럼이 등록일

        try:
            # YYYY-MM-DD 형식으로 파싱
            published = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=kst)
        except ValueError:
            # 날짜 파싱 실패 시 현재 날짜 사용
            published = datetime.now(kst)

        result = {
            "title": title,
            "link": link,
            "published": published.isoformat(),
            "scraper_type": "climatechange_academic",
        }

        return result

    except Exception as e:
        print(f"❌ [PARSE] 공지사항 파싱 중 오류: {e}")
        return None
