from bs4 import BeautifulSoup
from datetime import datetime
from template.notice_data import NoticeData
from utils.scraper_type import ScraperType
from utils.web_scraper import WebScraper
from config.logger_config import setup_logger

logger = setup_logger(__name__)


class DesignMetalworkAcademicScraper(WebScraper):
    """금속공예학과 학사공지 스크래퍼"""

    def __init__(self, url: str):
        super().__init__(url, ScraperType.DESIGN_METALWORK_ACADEMIC)

    def get_list_elements(self, soup: BeautifulSoup) -> list:
        """공지사항 목록의 HTML 요소들을 가져옵니다."""
        return soup.select("#kboard-default-list .kboard-list tbody tr")

    async def parse_notice_from_element(self, element) -> NoticeData:
        """HTML 요소에서 공지사항 정보를 추출합니다."""
        try:
            # 공지사항 여부 확인
            is_notice = "kboard-list-notice" in element.get("class", [])

            # 제목과 링크 추출
            title_element = element.select_one(".kboard-list-title div.cut_strings a")
            if not title_element:
                return None

            title = title_element.get_text(strip=True)
            relative_link = title_element.get("href", "")

            # 상대 경로를 절대 경로로 변환
            if relative_link.startswith("/?"):
                link = f"http://mcraft.kookmin.ac.kr{relative_link}"
            else:
                link = relative_link

            # 날짜 추출
            date_str = element.select_one(".kboard-list-date").get_text(strip=True)

            try:
                published = datetime.strptime(date_str, "%Y.%m.%d").replace(
                    tzinfo=self.kst
                )
            except ValueError:
                try:
                    published = datetime.strptime(date_str, "%Y-%m-%d").replace(
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
