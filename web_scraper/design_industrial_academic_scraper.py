from bs4 import BeautifulSoup
from datetime import datetime
from template.notice_data import NoticeData
from utils.scraper_type import ScraperType
from utils.web_scraper import WebScraper
from config.logger_config import setup_logger

logger = setup_logger(__name__)


class DesignIndustrialAcademicScraper(WebScraper):
    """공업디자인학과 학사공지 스크래퍼"""

    def __init__(self, url: str):
        super().__init__(url, ScraperType.DESIGN_INDUSTRIAL_ACADEMIC)

    def get_list_elements(self, soup: BeautifulSoup) -> list:
        """공지사항 목록의 HTML 요소들을 가져옵니다."""
        return soup.select("table.board-table tbody tr")

    async def parse_notice_from_element(self, element) -> NoticeData:
        """HTML 요소에서 공지사항 정보를 추출합니다."""
        try:
            # 공지사항 여부 확인
            is_notice = element.select_one(".num-notice") is not None

            # 제목과 링크 추출
            title_element = element.select_one(".b-title-box a")
            if not title_element:
                return None

            title = title_element.get_text(strip=True)
            relative_link = title_element.get("href", "")

            # 상대 경로를 절대 경로로 변환
            if relative_link.startswith("?"):
                link = f"http://cms.kookmin.ac.kr/id/intro/notice.do{relative_link}"
            else:
                link = relative_link

            # 날짜 추출
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
