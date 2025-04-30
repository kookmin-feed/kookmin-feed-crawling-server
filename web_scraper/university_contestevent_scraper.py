from bs4 import BeautifulSoup
from datetime import datetime
import aiohttp
import re
from template.notice_data import NoticeData
from utils.scraper_type import ScraperType
from utils.web_scraper import WebScraper
from config.logger_config import setup_logger

logger = setup_logger(__name__)


class UniversityContesteventScraper(WebScraper):
    """대학 공모행사공지 스크래퍼"""

    def __init__(self, url: str):
        super().__init__(url, ScraperType.UNIVERSITY_CONTESTEVENT)
        self.base_url = "https://www.kookmin.ac.kr"

    def get_list_elements(self, soup: BeautifulSoup) -> list:
        """공모행사공지 목록의 HTML 요소들을 가져옵니다."""
        # 일반 게시물과 공지사항 모두 가져옴
        elements = soup.select("div.board_list > ul > li")
        return elements if elements else []

    async def parse_notice_from_element(self, element) -> NoticeData:
        """HTML 요소에서 공모행사공지 정보를 추출합니다."""
        try:
            # 공지사항 여부 확인
            is_notice = "notice" in element.get("class", [])

            # 제목과 링크 추출 - 공지사항과 일반 게시물의 구조가 다름
            a_tag = element.select_one("a")
            if not a_tag:
                return None

            relative_link = a_tag.get("href", "")
            # 상대 경로를 절대 경로로 변환
            if relative_link.startswith("/"):
                link = f"{self.base_url}{relative_link}"
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
                published = await self.get_date_from_detail_page(link)
            else:
                # 일반 게시물은 목록에서 날짜 추출
                date_element = element.select_one("div.board_etc span:first-child")
                if not date_element:
                    # 날짜를 찾을 수 없는 경우 상세 페이지에서 가져옴
                    published = await self.get_date_from_detail_page(link)
                else:
                    date_str = date_element.get_text(strip=True)
                    try:
                        # YYYY.MM.DD 형식
                        published = datetime.strptime(date_str, "%Y.%m.%d").replace(
                            tzinfo=self.kst
                        )
                    except ValueError:
                        try:
                            # YYYY-MM-DD 형식
                            published = datetime.strptime(date_str, "%Y-%m-%d").replace(
                                tzinfo=self.kst
                            )
                        except ValueError:
                            # 날짜 형식이 다른 경우 상세 페이지에서 가져옴
                            published = await self.get_date_from_detail_page(link)

            # 공지사항인 경우 제목 앞에 [공지] 표시 추가
            if is_notice and not title.startswith("[공지]"):
                title = f"[공지] {title}"

            return NoticeData(
                title=title,
                link=link,
                published=published,
                scraper_type=self.scraper_type,
            )

        except Exception as e:
            logger.error(f"공지사항 파싱 중 오류: {e}")
            return None

    async def get_date_from_detail_page(self, url: str) -> datetime:
        """상세 페이지에서 날짜 정보를 추출합니다."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.error(
                            f"상세 페이지 요청 실패: {url}, 상태 코드: {response.status}"
                        )
                        # 현재 시간을 기본값으로 사용
                        return datetime.now(self.kst)

                    html = await response.text()
                    soup = BeautifulSoup(html, "html.parser")

                    # 상세 페이지에서 날짜 요소 찾기 - view_top > board_etc > 작성일 span
                    date_element = soup.select_one(
                        "div.view_top div.board_etc span:first-child"
                    )
                    if not date_element:
                        logger.warning(
                            f"상세 페이지에서 날짜 요소를 찾을 수 없음: {url}"
                        )
                        return datetime.now(self.kst)

                    date_str = date_element.get_text(strip=True)
                    # "작성일 2025.03.07" 형식에서 날짜만 추출
                    date_match = re.search(
                        r"작성일\s+(\d{4}[-\.]\d{1,2}[-\.]\d{1,2})", date_str
                    )
                    if date_match:
                        date_str = date_match.group(1)
                    else:
                        # 다른 형식일 수 있으므로 일반적인 날짜 패턴 검색
                        date_match = re.search(
                            r"(\d{4}[-\.]\d{1,2}[-\.]\d{1,2})", date_str
                        )
                        if date_match:
                            date_str = date_match.group(1)
                        else:
                            logger.warning(f"날짜 형식을 인식할 수 없음: {date_str}")
                            return datetime.now(self.kst)

                    try:
                        # YYYY.MM.DD 형식
                        if "." in date_str:
                            return datetime.strptime(date_str, "%Y.%m.%d").replace(
                                tzinfo=self.kst
                            )
                        # YYYY-MM-DD 형식
                        else:
                            return datetime.strptime(date_str, "%Y-%m-%d").replace(
                                tzinfo=self.kst
                            )
                    except ValueError as e:
                        logger.error(f"날짜 파싱 오류: {date_str}, {e}")
                        return datetime.now(self.kst)
        except Exception as e:
            logger.error(f"상세 페이지 요청 중 오류: {e}")
            return datetime.now(self.kst)
