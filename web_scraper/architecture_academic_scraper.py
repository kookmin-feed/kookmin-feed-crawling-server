from bs4 import BeautifulSoup
from datetime import datetime
from template.notice_data import NoticeData
from utils.scraper_type import ScraperType
from utils.web_scraper import WebScraper
from config.logger_config import setup_logger

logger = setup_logger(__name__)


class ArchitectureAcademicScraper(WebScraper):
    """건축대학 단과대공지 스크래퍼"""

    def __init__(self, url: str):
        super().__init__(url, ScraperType.ARCHITECTURE_ACADEMIC)

    def get_list_elements(self, soup: BeautifulSoup) -> list:
        """건축대학 공지사항 목록의 HTML 요소들을 가져옵니다."""
        return soup.select(".board-list-type01 li")

    async def parse_notice_from_element(self, element) -> NoticeData:
        """HTML 요소에서 건축대학 공지사항 정보를 추출합니다."""
        try:
            # 공지사항 링크 태그 찾기
            link_tag = element.select_one("a")
            if not link_tag:
                return None

            # 제목 추출
            title_tag = element.select_one(".borad-list-tit")
            if not title_tag:
                return None

            title = title_tag.text.strip()

            # 링크 생성
            href = link_tag.get("href", "")
            link = f"https://archi.kookmin.ac.kr/life/notice/{href}"

            # 날짜 추출
            date_tag = element.select_one(".board-list-date")
            if not date_tag:
                return None

            date = date_tag.text.strip()
            published = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=self.kst)

            return NoticeData(
                title=title,
                link=link,
                published=published,
                scraper_type=self.scraper_type,
            )
        except Exception as e:
            logger.error(f"공지사항 파싱 중 오류: {e}")
            return None
