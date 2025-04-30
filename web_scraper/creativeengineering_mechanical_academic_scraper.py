from bs4 import BeautifulSoup
from datetime import datetime
from template.notice_data import NoticeData
from utils.scraper_type import ScraperType
from utils.web_scraper import WebScraper
from config.logger_config import setup_logger

logger = setup_logger(__name__)


class CreativeengineeringMechanicalAcademicScraper(WebScraper):
    """기계공학부 학사공지 스크래퍼"""

    def __init__(self, url: str):
        super().__init__(url, ScraperType.CREATIVEENGINEERING_MECHANICAL_ACADEMIC)

    def get_list_elements(self, soup: BeautifulSoup) -> list:
        """기계공학부 공지사항 목록의 HTML 요소들을 가져옵니다."""
        return soup.select("table.board-table tbody tr")

    async def parse_notice_from_element(self, row) -> NoticeData:
        """HTML 요소에서 기계공학부 공지사항 정보를 추출합니다."""
        try:
            # 제목 셀 찾기
            title_cell = row.select_one(".b-td-left")
            if not title_cell:
                return None

            # 제목과 링크 추출
            title_link = title_cell.select_one("a")
            if not title_link:
                return None

            title = title_link.get_text(strip=True)
            link = f"http://cms.kookmin.ac.kr/mech/bbs/notice.do{title_link['href']}"

            # 날짜 추출 (마지막 td 요소)
            date = row.select("td")[-1].get_text(strip=True)

            try:
                published = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=self.kst)
            except ValueError:
                try:
                    published = datetime.strptime(date, "%Y.%m.%d").replace(
                        tzinfo=self.kst
                    )
                except ValueError:
                    published = datetime.strptime(date, "%y.%m.%d").replace(
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
