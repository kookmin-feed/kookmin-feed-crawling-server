from datetime import datetime
from bs4 import BeautifulSoup
from template.notice_data import NoticeData
from utils.scraper_type import ScraperType
from utils.web_scraper import WebScraper
from config.logger_config import setup_logger

logger = setup_logger(__name__)


class LawAcademicScraper(WebScraper):
    """법과대학 학사공지 스크래퍼"""

    def __init__(self, url: str):
        super().__init__(url, ScraperType.LAW_ACADEMIC)

    def get_list_elements(self, soup: BeautifulSoup) -> list:
        """공지사항 목록의 HTML 요소들을 가져옵니다."""
        # board-table 내의 모든 tr 요소를 가져옴
        elements = soup.select("table.board-table tbody tr")
        return elements if elements else []

    async def parse_notice_from_element(self, element) -> NoticeData:
        """HTML 요소에서 공지사항 정보를 추출합니다."""
        try:
            # 제목과 링크 추출
            title_cell = element.select_one(".b-td-left")
            if not title_cell:
                return None

            title_element = title_cell.select_one(".b-title-box a")
            if not title_element:
                return None

            title = title_element.get_text(strip=True)
            relative_link = title_element.get("href", "")

            # 상대 경로를 절대 경로로 변환
            if relative_link.startswith("?"):
                link = f"https://law.kookmin.ac.kr/law/etc-board/notice01.do{relative_link}"
            else:
                link = relative_link

            # 날짜 추출 (td 요소 중 작성일 항목)
            date_str = element.select("td")[-2].get_text(strip=True)

            try:
                published = datetime.strptime(date_str, "%Y-%m-%d").replace(
                    tzinfo=self.kst
                )
            except ValueError:
                try:
                    published = datetime.strptime(date_str, "%Y.%m.%d").replace(
                        tzinfo=self.kst
                    )
                except ValueError:
                    published = datetime.strptime(date_str, "%y.%m.%d").replace(
                        tzinfo=self.kst
                    )

            return NoticeData(
                title=title,
                link=link,
                published=published,
                scraper_type=self.scraper_type,
            )

        except Exception as e:
            logger.error(f"공지사항 파싱 중 오류: {e}")
            return None
