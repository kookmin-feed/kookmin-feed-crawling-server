from bs4 import BeautifulSoup
from datetime import datetime
from template.notice_data import NoticeData
from utils.scraper_type import ScraperType
from utils.web_scraper import WebScraper
from config.logger_config import setup_logger

logger = setup_logger(__name__)


class SciencetechnologyChemistryAcademicScraper(WebScraper):
    """응용화학부 학사공지 스크래퍼"""

    def __init__(self, url: str):
        super().__init__(url, ScraperType.SCIENCETECHNOLOGY_CHEMISTRY_ACADEMIC)
        self.base_url = "http://chem.kookmin.ac.kr"

    def get_list_elements(self, soup: BeautifulSoup) -> list:
        """학사공지 목록의 HTML 요소들을 가져옵니다."""
        table = soup.select_one("div#ezsBBS table")
        if not table:
            self.logger.error("테이블을 찾을 수 없습니다")
            return []

        rows = table.select("tr")
        self.logger.debug(f"테이블에서 총 {len(rows)} 개의 행을 찾았습니다")

        # 헤더 행을 제외한 모든 행 반환
        return rows[1:] if len(rows) > 1 else []

    async def parse_notice_from_element(self, element) -> NoticeData:
        """HTML 요소에서 학사공지 정보를 추출합니다."""
        try:
            # 제목과 링크 추출
            title_link = element.select_one("td ul li a.Board")
            if not title_link:
                return None

            title = title_link.text.strip()
            relative_link = title_link.get("href", "")

            # 상대 경로를 절대 경로로 변환
            if relative_link.startswith("/"):
                link = f"{self.base_url}{relative_link}"
            else:
                link = f"{self.base_url}/sub6/{relative_link}"

            # 날짜 추출
            date_cells = element.select("td.txtc.txtN")
            if len(date_cells) >= 3:  # 번호, 날짜, 조회수 순서로 있을 것으로 예상
                date_str = date_cells[1].text.strip()
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
                        logger.error(f"날짜 파싱 오류: {date_str}")
                        published = datetime.now(self.kst)
            else:
                logger.warning("날짜 요소를 찾을 수 없음")
                published = datetime.now(self.kst)

            return NoticeData(
                title=title,
                link=link,
                published=published,
                scraper_type=self.scraper_type,
            )
        except Exception as e:
            logger.error(f"공지사항 파싱 중 오류: {e}")
            return None
