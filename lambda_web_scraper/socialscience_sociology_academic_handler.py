import json

from datetime import datetime, timedelta
import pytz
from typing import Dict, Any
import re
from common_utils import (
    fetch_page,
    get_recent_notices,
    save_notices_to_db,
    send_slack_notification,
)


def handler(event, context):
    """
    사회학과 학사공지 스크래퍼 Lambda Handler
    깔끔하고 독립적인 구현
    """

    print("🚀 [HANDLER] Lambda Handler 시작")

    try:
        # 동기 스크래퍼 실행
        result = scrape_socialscience_sociology_academic()

        return {
            "statusCode": 200,
        }

    except Exception as e:
        error_msg = f"Lambda Handler 실행 중 오류: {str(e)}"
        print(f"❌ [HANDLER] {error_msg}")
        send_slack_notification(error_msg, "socialscience_sociology_academic")
        return {
            "statusCode": 500,
        }


def scrape_socialscience_sociology_academic() -> Dict[str, Any]:
    """
    사회학과 학사공지를 스크래핑하고 새로운 공지사항을 처리
    """

    url = "https://kmusoc.kookmin.ac.kr/kmusoc/etc-board/major_notice.do"
    kst = pytz.timezone("Asia/Seoul")

    print(f"🌐 [SCRAPER] 스크래핑 시작 - URL: {url}")

    try:
        # 웹페이지 가져오기
        soup = fetch_page(url)

        # 공지사항 목록 요소들 가져오기
        elements = soup.select("tbody tr")
        print(f"📊 [SCRAPER] 발견된 공지사항 수: {len(elements)}")

        # 기존 공지사항 확인 (MongoDB에서)
        recent_notices = get_recent_notices("socialscience_sociology_academic")
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
            saved_count = save_notices_to_db(
                new_notices, "socialscience_sociology_academic"
            )
            print(f"💾 [SCRAPER] 저장 완료: {saved_count}개")

        result = {
            "success": True,
            "message": f"사회학과 학사공지 스크래핑 완료",
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
        send_slack_notification(error_msg, "socialscience_sociology_academic")
        return {"success": False, "error": error_msg}


def parse_notice_from_element(element, kst) -> Dict[str, Any]:
    """HTML 요소에서 사회학과 학사공지 정보를 추출"""

    try:
        # 상단 고정 공지 여부 확인
        notice_box = element.select_one(".b-num-box")
        is_top_notice = notice_box and "num-notice" in notice_box.get("class", [])

        # 제목과 링크 추출
        title_element = element.select_one(".b-title-box a")
        if not title_element:
            print("❌ [PARSE] 제목 요소를 찾을 수 없습니다.")
            return None

        # 제목 텍스트 정리 - 불필요한 공백과 줄바꿈 제거
        title = title_element.get_text(strip=True)
        # 추가 정리: 연속된 공백을 하나로 치환
        title = re.sub(r"\s+", " ", title).strip()

        # "자세히 보기" 텍스트 제거
        title = re.sub(r" 자세히 보기$", "", title)

        # 만약 제목이 여전히 "..."로 끝나면 원본 title 속성 확인
        if title.endswith("..."):
            # title 속성에서 완전한 제목을 가져오려고 시도
            full_title = title_element.get("title", "")
            if full_title and "자세히 보기" in full_title:
                # title 속성에서 "자세히 보기" 부분 제거
                title = re.sub(r" 자세히 보기$", "", full_title)

        # 상단 고정 공지는 제목에 [공지] 표시 추가 (없는 경우에만)
        if is_top_notice and not title.startswith("[공지]"):
            title = f"[공지] {title}"

        # 링크 처리 (상대 경로인 경우 기본 URL과 결합)
        link_href = title_element.get("href", "")
        if link_href.startswith("?"):
            base_url = "https://kmusoc.kookmin.ac.kr/kmusoc/etc-board/major_notice.do"
            link = f"{base_url}{link_href}"
        else:
            link = link_href

        # 날짜 추출
        date_element = element.select_one(".b-date")
        if not date_element:
            print("❌ [PARSE] 날짜 요소를 찾을 수 없습니다.")
            published = datetime.now(kst)
        else:
            date_text = date_element.text.strip()
            # YY.MM.DD 형식 파싱 (예: 25.02.26)
            date_match = re.search(r"(\d{2})\.(\d{2})\.(\d{2})", date_text)
            if date_match:
                year, month, day = date_match.groups()
                # 20년대로 가정
                year = "20" + year
                published = datetime.strptime(
                    f"{year}-{month}-{day}", "%Y-%m-%d"
                ).replace(tzinfo=kst)
            else:
                print(f"❌ [PARSE] 날짜 형식 변환 실패: {date_text}")
                published = datetime.now(kst)

        # NEW 표시 확인 (추가 기능)
        is_new = bool(element.select_one(".b-new"))
        if is_new:
            print(f"🆕 [PARSE] 새 게시물 발견: {title}")

        # 로깅
        if is_top_notice:
            print(f"📌 [PARSE] 상단 고정 공지 파싱: {title}")
        else:
            print(f"📄 [PARSE] 일반 공지 파싱: {title}")

        result = {
            "title": title,
            "link": link,
            "published": published.isoformat(),
            "scraper_type": "socialscience_sociology_academic",
        }

        return result

    except Exception as e:
        print(f"❌ [PARSE] 공지사항 파싱 중 오류: {e}")
        return None
