import re
from datetime import datetime
from bs4 import BeautifulSoup
from template.notice_data import NoticeData
from utils.scraper_type import ScraperType
from utils.web_scraper import WebScraper
from config.logger_config import setup_logger

logger = setup_logger(__name__)


class CreativeengineeringCivilAcademicScraper(WebScraper):
    """건설시스템공학부 학사공지 스크래퍼"""

    def __init__(self, url: str):
        super().__init__(url, ScraperType.CREATIVEENGINEERING_CIVIL_ACADEMIC)

    def get_list_elements(self, soup: BeautifulSoup) -> list:
        """공지사항 목록을 가져옵니다."""
        # 공지사항 목록 선택 (상단 고정 공지 포함)
        notice_list = soup.select("tbody tr")
        return notice_list

    async def parse_notice_from_element(self, element) -> NoticeData:
        """개별 공지사항 정보를 파싱합니다."""
        try:
            # 상단 고정 공지 여부 확인
            is_top_notice = "b-top-box" in element.get("class", [])

            title_element = element.select_one(".b-title-box a")

            title = title_element.text.strip() if title_element else "제목 없음"
            # 상단 고정 공지는 제목 앞에 [공지] 표시 추가
            if is_top_notice and not title.startswith("[공지]"):
                title = f"[공지] {title}"

            link = (
                self.url.split("?")[0] + title_element["href"] if title_element else ""
            )

            date_text = (
                element.select_one(".b-date").text.strip()
                if element.select_one(".b-date")
                else ""
            )

            # 날짜 포맷 변환 (YY.MM.DD → YYYY-MM-DD)
            if date_text:
                date_match = re.search(r"(\d{2})\.(\d{2})\.(\d{2})", date_text)
                if date_match:
                    year, month, day = date_match.groups()
                    # 20년대로 가정
                    year = "20" + year
                    published = datetime.strptime(f"{year}-{month}-{day}", "%Y-%m-%d")
                else:
                    published = datetime.now()
            else:
                published = datetime.now()

            # 공지 여부 로깅
            if is_top_notice:
                logger.debug(f"상단 고정 공지 파싱 완료: {title}")

            return NoticeData(title, link, published, self.scraper_type)

        except Exception as e:
            logger.error(f"공지사항 파싱 중 오류: {e}")
            return None
