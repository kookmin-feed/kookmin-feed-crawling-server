from bs4 import BeautifulSoup
from datetime import datetime
from template.notice_data import NoticeData
from utils.scraper_type import ScraperType
from utils.web_scraper import WebScraper
from config.logger_config import setup_logger

logger = setup_logger(__name__)


class LincAcademicScraper(WebScraper):
    """LINC 3.0 사업단 공지사항 스크래퍼"""

    def __init__(self, url: str):
        super().__init__(url, ScraperType.LINC_ACADEMIC)

    def get_list_elements(self, soup: BeautifulSoup) -> list:
        """공지사항 목록의 HTML 요소들을 가져옵니다."""
        return soup.select(".board_list .content_wrap li")

    async def parse_notice_from_element(self, element) -> NoticeData:
        """HTML 요소에서 공지사항 정보를 추출합니다."""
        try:
            # 공지사항 여부 확인
            is_notice = element.select_one(".icon_notice") is not None

            # 제목과 링크 추출
            title_element = element.select_one("a")
            if not title_element:
                return None

            title = title_element.select_one(".tit0").get_text(strip=True)

            # 상대 경로 추출 및 URL 생성
            relative_link = title_element.get("href", "")
            if relative_link.startswith("https://"):
                link = relative_link
            else:
                link = (
                    f"https://linc.kookmin.ac.kr/main/menu{relative_link[1:]}"
                    if relative_link.startswith("/")
                    else f"https://linc.kookmin.ac.kr/main/menu{relative_link}"
                )

            # 날짜 추출
            date_str = element.select_one(".date").get_text(strip=True)

            try:
                published = datetime.strptime(date_str, "%Y-%m-%d").replace(
                    tzinfo=self.kst
                )
            except ValueError:
                published = datetime.strptime(date_str, "%Y.%m.%d").replace(
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
