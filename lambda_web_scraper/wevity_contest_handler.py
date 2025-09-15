import re
from datetime import datetime, timedelta
from typing import Dict, Any
import pytz

from common_utils import (
    fetch_page,
    get_recent_notices,
    save_notices_to_db,
    send_slack_notification,
)


def parse_date(date_str: str, kst: pytz.timezone) -> datetime:
    """
    날짜 문자열을 파싱하여 datetime 객체로 변환
    """
    try:
        # "D-60" 형식 파싱
        if "D-" in date_str:
            days_match = re.search(r"D-(\d+)", date_str)
            if days_match:
                days = int(days_match.group(1))
                return datetime.now(kst) + timedelta(days=days)

        # 기본값: 현재 시간
        return datetime.now(kst)
    except Exception as e:
        print(f"⚠️ [PARSER] 날짜 파싱 실패: {date_str}, 오류: {e}")
        return datetime.now(kst)


def scrape_wevity_contest() -> Dict[str, Any]:
    """
    위비티 공모전을 스크래핑하고 새로운 공모전을 처리
    """
    url = "https://www.wevity.com/?c=find&s=1&gub=1&cidx=20&gbn=list"
    kst = pytz.timezone("Asia/Seoul")

    print(f"🌐 [SCRAPER] 스크래핑 시작 - URL: {url}")

    try:
        # 웹페이지 가져오기
        soup = fetch_page(url)

        # 공모전 목록 요소들 가져오기
        elements = soup.select("ul.list li:not(.top)")
        print(f"📊 [SCRAPER] 발견된 공모전 수: {len(elements)}")

        # 기존 공모전 확인 (MongoDB에서)
        recent_notices = get_recent_notices("wevity_contest")
        recent_links = {notice.get("link") for notice in recent_notices}
        recent_titles = {notice.get("title") for notice in recent_notices}

        # 새로운 공모전 파싱
        new_contests = []

        for element in elements:
            contest = parse_contest_from_element(element, kst)
            if contest:
                # 30일 이내의 데이터만 필터링
                thirty_days_ago = datetime.now(kst) - timedelta(days=30)
                published_date = datetime.fromisoformat(
                    contest["published"].replace("Z", "+00:00")
                )
                if published_date >= thirty_days_ago:
                    # 중복 확인
                    if (
                        contest["link"] not in recent_links
                        and contest["title"] not in recent_titles
                    ):
                        new_contests.append(contest)
                        print(f"🆕 [SCRAPER] 새로운 공모전: {contest['title'][:30]}...")
                else:
                    print(
                        f"⏰ [SCRAPER] 30일 이전 공모전 제외: {contest['title'][:30]}..."
                    )

        print(f"📈 [SCRAPER] 새로운 공모전 수: {len(new_contests)}")

        # 새로운 공모전을 MongoDB에 저장
        saved_count = 0
        if new_contests:
            saved_count = save_notices_to_db(new_contests, "wevity_contest")
            print(f"💾 [SCRAPER] 저장 완료: {saved_count}개")

        result = {
            "success": True,
            "message": f"위비티 공모전 스크래핑 완료",
            "total_found": len(elements),
            "new_notices_count": len(new_contests),
            "saved_count": saved_count,
            "new_notices": new_contests,
        }

        print(f"🎉 [SCRAPER] 스크래핑 완료")
        return result

    except Exception as e:
        error_msg = f"스크래핑 중 오류: {str(e)}"
        print(f"❌ [SCRAPER] {error_msg}")
        send_slack_notification(error_msg, "wevity_contest")
        return {"success": False, "error": error_msg}


def parse_contest_from_element(element, kst) -> Dict[str, Any]:
    """HTML 요소에서 공모전 정보를 추출"""

    try:
        # 제목 추출
        title_tag = element.select_one("div.tit a")
        if not title_tag:
            return None

        title = title_tag.get_text(strip=True)
        # SPECIAL, IDEA 태그 제거
        title = re.sub(r"\s*<span[^>]*>.*?</span>", "", title)

        # 링크 추출
        link = title_tag.get("href")
        if link:
            # 상대 경로를 절대 경로로 변환
            if link.startswith("?"):
                base_url = "https://www.wevity.com/"
                link = base_url + link

        # 마감일 정보 추출
        day_element = element.select_one("div.day")
        deadline = day_element.get_text(strip=True) if day_element else None

        # 마감일 파싱하여 published_date 생성
        published = parse_date(deadline, kst) if deadline else datetime.now(kst)

        result = {
            "title": title,
            "link": link,
            "published": published.isoformat(),
            "scraper_type": "wevity_contest",
        }

        return result

    except Exception as e:
        print(f"❌ [PARSE] 공모전 파싱 중 오류: {e}")
        return None


def handler(event, context):
    """
    위비티 공모전 스크래퍼 Lambda Handler
    깔끔하고 독립적인 구현
    """

    print("🚀 [HANDLER] Lambda Handler 시작")

    try:
        # 동기 스크래퍼 실행
        result = scrape_wevity_contest()

        return {
            "statusCode": 200,
        }

    except Exception as e:
        error_msg = f"Lambda Handler 실행 중 오류: {str(e)}"
        print(f"❌ [HANDLER] {error_msg}")
        send_slack_notification(error_msg, "wevity_contest")
        return {
            "statusCode": 500,
        }
