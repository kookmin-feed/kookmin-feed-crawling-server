import re
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
    북악정치포럼 스크래퍼 Lambda Handler
    깔끔하고 독립적인 구현
    """

    print("🚀 [HANDLER] Lambda Handler 시작")

    try:
        # 동기 스크래퍼 실행
        result = scrape_university_bukakpoliticalforum()

        return {
            "statusCode": 200,
        }

    except Exception as e:
        error_msg = f"Lambda Handler 실행 중 오류: {str(e)}"
        print(f"❌ [HANDLER] {error_msg}")
        send_slack_notification(error_msg, "university_bukakpoliticalforum")
        return {
            "statusCode": 500,
        }


def scrape_university_bukakpoliticalforum() -> Dict[str, Any]:
    """
    북악정치포럼을 스크래핑하고 새로운 공지사항을 처리
    """

    url = "https://www.kookmin.ac.kr/user/kmuNews/specBbs/bugAgForum/index.do"
    kst = pytz.timezone("Asia/Seoul")

    print(f"🌐 [SCRAPER] 스크래핑 시작 - URL: {url}")

    try:
        # 웹페이지 가져오기
        soup = fetch_page(url)

        # 공지사항 목록 요소들 가져오기
        elements = soup.select(".board_list ul li")
        print(f"📊 [SCRAPER] 발견된 공지사항 수: {len(elements)}")

        # 기존 공지사항 확인 (MongoDB에서)
        recent_notices = get_recent_notices("university_bukakpoliticalforum")
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
                new_notices, "university_bukakpoliticalforum"
            )
            print(f"💾 [SCRAPER] 저장 완료: {saved_count}개")

        result = {
            "success": True,
            "message": f"북악정치포럼 스크래핑 완료",
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
        send_slack_notification(error_msg, "university_bukakpoliticalforum")
        return {"success": False, "error": error_msg}


def parse_notice_from_element(element, kst) -> Dict[str, Any]:
    """HTML 요소에서 북악정치포럼 정보를 추출"""

    try:
        # a 태그 추출
        a_tag = element.select_one("a")
        if not a_tag:
            print("❌ [PARSE] a 태그를 찾을 수 없습니다.")
            return None

        # 제목 추출
        title_tag = a_tag.select_one("p.title")
        if not title_tag:
            print("❌ [PARSE] 제목 요소를 찾을 수 없습니다.")
            return None

        title = title_tag.text.strip()

        # 작성자 추출
        author_element = a_tag.select_one("p.desc")
        author = author_element.text.strip() if author_element else ""
        if author:
            title = f"[{author}] {title}"

        # 회차 정보 추출 후 제목에 추가
        category_element = a_tag.select_one(".ctg_name em")
        category = category_element.text.strip() if category_element else ""
        if category:
            title = f"[{category}] {title}"

        # 날짜와 장소 추출
        board_etc = a_tag.select_one(".board_etc")
        if board_etc:
            spans = board_etc.select("span")
            if spans and len(spans) > 0:
                # 날짜 추출 및 변환
                date_text = spans[0].text.strip().replace("일시 및 기간: ", "")
                try:
                    # "2025.04.29 (18:45~20:15)" 또는 "2025.04.29 (18:45 ~ 20:15)" 형식에서 날짜 부분만 추출
                    date_match = re.search(r"(\d{4})\.(\d{2})\.(\d{2})", date_text)
                    if date_match:
                        year, month, day = date_match.groups()
                        published = datetime.strptime(
                            f"{year}-{month}-{day}", "%Y-%m-%d"
                        ).replace(tzinfo=kst)
                    else:
                        print(f"❌ [PARSE] 날짜 형식 변환 실패: {date_text}")
                        published = datetime.now(kst)
                except ValueError as e:
                    print(f"❌ [PARSE] 날짜 파싱 오류: {e}")
                    published = datetime.now(kst)

                # 장소 정보 추출 (사용하지 않지만 레거시 코드와 호환성 유지)
                location = spans[1].text.strip() if len(spans) > 1 else ""
            else:
                published = datetime.now(kst)
                location = ""
        else:
            published = datetime.now(kst)
            location = ""

        # 링크 추출
        onclick = a_tag.get("onclick", "")
        if "global.write(" in onclick:
            # onclick="global.write('58873', './view.do');" 에서 post_id 추출
            parts = onclick.split("'")
            if len(parts) >= 2:
                post_id = parts[1]
                link = f"https://www.kookmin.ac.kr/user/kmuNews/specBbs/bugAgForum/view.do?dataSeq={post_id}"
            else:
                link = (
                    "https://www.kookmin.ac.kr/user/kmuNews/specBbs/bugAgForum/index.do"
                )
        else:
            link = "https://www.kookmin.ac.kr/user/kmuNews/specBbs/bugAgForum/index.do"

        # 로깅
        print(f"📝 [PARSE] 공지사항 파싱: {title[:50]}...")

        result = {
            "title": title,
            "link": link,
            "published": published.isoformat(),
            "scraper_type": "university_bukakpoliticalforum",
        }

        return result

    except Exception as e:
        print(f"❌ [PARSE] 공지사항 파싱 중 오류: {e}")
        return None
