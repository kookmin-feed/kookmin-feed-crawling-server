from bs4 import BeautifulSoup, Tag
from utils.web_scraper import WebScraper
from template.notice_data import NoticeData
from utils.scraper_type import ScraperType
from datetime import datetime


class AutomativeengineeringAcademicScraper(WebScraper):
    """자동차융합대학 학사공지 스크래퍼"""

    def __init__(self, url: str):
        super().__init__(url, ScraperType.AUTOMATIVEENGINEERING_ACADEMIC)

    def get_list_elements(self, soup: BeautifulSoup) -> list[Tag]:
        """공지사항 목록의 각 요소를 가져옵니다."""

        return soup.select("div.list-type01.list-l ul li")

    async def parse_notice_from_element(self, element: Tag) -> NoticeData | None:
        """각 공지사항 요소에서 정보를 추출하여 NoticeData 객체를 생성합니다."""
        try:
            # list-type01-box 클래스 확인
            box_div = element.select_one("div.list-type01-box")
            if not box_div:
                return None

            # 링크와 ID 추출
            link_tag = element.select_one("a")
            if not link_tag:
                raise ValueError("링크를 찾을 수 없습니다")

            link = link_tag.get("href", "")
            if not link:
                raise ValueError("링크 주소를 찾을 수 없습니다")

            # 제목 추출
            title_tag = element.select_one("strong.list01-tit")
            if not title_tag:
                raise ValueError("제목을 찾을 수 없습니다")
            title = title_tag.text.strip()

            # 날짜 추출
            date_tag = element.select_one("span.list01-date")
            if not date_tag:
                raise ValueError("날짜를 찾을 수 없습니다")
            date_str = date_tag.text.strip()
            date = datetime.strptime(date_str, "%Y.%m.%d")

            # 전체 URL 생성
            full_url = f"https://auto.kookmin.ac.kr/board/notice/{link}"

            return NoticeData(
                title=title,
                link=full_url,
                published=date,
                scraper_type=self.scraper_type,
            )

        except Exception as e:
            self.logger.error(f"공지사항 파싱 중 오류: {str(e)}")
            raise
