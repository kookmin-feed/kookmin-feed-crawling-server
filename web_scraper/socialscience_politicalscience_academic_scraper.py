import re
from datetime import datetime
from bs4 import BeautifulSoup
from template.notice_data import NoticeData
from utils.scraper_type import ScraperType
from utils.web_scraper import WebScraper
from config.logger_config import setup_logger

logger = setup_logger(__name__)


class SocialsciencePoliticalscienceAcademicScraper(WebScraper):
    """정치외교학과 학사공지 스크래퍼"""

    def __init__(self, url: str):
        super().__init__(url, ScraperType.SOCIALSCIENCE_POLITICALSCIENCE_ACADEMIC)

    def get_list_elements(self, soup: BeautifulSoup) -> list:
        """공지사항 목록을 가져옵니다."""
        notice_list = soup.select("tbody tr")
        return notice_list

    async def parse_notice_from_element(self, element) -> NoticeData:
        """개별 공지사항 정보를 파싱합니다."""
        try:
            # 상단 고정 공지 여부 확인 (공지 표시가 있는지 확인)
            notice_box = element.select_one(".b-num-box")
            is_top_notice = notice_box and "num-notice" in notice_box.get("class", [])

            # 제목과 링크 추출
            title_element = element.select_one(".b-title-box a")
            if not title_element:
                logger.warning("제목 요소를 찾을 수 없습니다.")
                return None

            title = title_element.text.strip()

            # 상단 고정 공지는 제목에 [공지] 표시 추가 (없는 경우에만)
            if is_top_notice and not title.startswith("[공지]"):
                title = f"[공지] {title}"

            # 링크 처리 (상대 경로인 경우 기본 URL과 결합)
            link_href = title_element.get("href", "")
            if link_href.startswith("?"):
                base_url = self.url.split("?")[0]
                link = f"{base_url}{link_href}"
            else:
                link = link_href

            # 날짜 추출
            date_element = element.select_one(".b-date")
            if not date_element:
                logger.warning("날짜 요소를 찾을 수 없습니다.")
                published = datetime.now()
            else:
                date_text = date_element.text.strip()
                # YY.MM.DD 형식 파싱 (예: 25.02.28)
                date_match = re.search(r"(\d{2})\.(\d{2})\.(\d{2})", date_text)
                if date_match:
                    year, month, day = date_match.groups()
                    # 20년대로 가정
                    year = "20" + year
                    published = datetime.strptime(f"{year}-{month}-{day}", "%Y-%m-%d")
                else:
                    logger.warning(f"날짜 형식 변환 실패: {date_text}")
                    published = datetime.now()

            # 로깅
            if is_top_notice:
                logger.debug(f"상단 고정 공지 파싱: {title}")
            else:
                logger.debug(f"일반 공지 파싱: {title}")

            return NoticeData(title, link, published, self.scraper_type)

        except Exception as e:
            logger.error(f"공지사항 파싱 중 오류: {e}")
            return None
