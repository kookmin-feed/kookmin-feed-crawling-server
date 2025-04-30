from bs4 import BeautifulSoup
from datetime import datetime
from template.notice_data import NoticeData
from utils.scraper_type import ScraperType
from utils.web_scraper import WebScraper
from config.logger_config import setup_logger

logger = setup_logger(__name__)


class SocialsciencePublicadministrationAcademicScraper(WebScraper):
    """행정학과 학사공지 스크래퍼"""

    def __init__(self, url: str):
        super().__init__(url, ScraperType.SOCIALSCIENCE_PUBLICADMINISTRATION_ACADEMIC)

    def get_list_elements(self, soup: BeautifulSoup) -> list:
        """행정학과 공지사항 목록의 HTML 요소들을 가져옵니다."""
        return soup.select("table.board-table tbody tr")

    async def parse_notice_from_element(self, row) -> NoticeData:
        """HTML 요소에서 행정학과 공지사항 정보를 추출합니다."""
        try:
            # 제목 셀 찾기
            title_cell = row.select_one(".b-td-left")
            if not title_cell:
                return None

            # 제목 링크 요소 찾기
            title_elem = title_cell.select_one(".b-title-box a")
            if not title_elem:
                return None

            # 제목과 링크 추출
            title = title_elem.text.strip()
            href = title_elem.get("href", "")

            # 게시글 번호 추출 및 전체 링크 생성
            article_no = (
                href.split("articleNo=")[1].split("&")[0]
                if "articleNo=" in href
                else ""
            )
            link = f"{self.url}?mode=view&articleNo={article_no}"

            # 날짜 추출 및 변환
            date = row.select_one("td:nth-last-child(2)").text.strip()

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
