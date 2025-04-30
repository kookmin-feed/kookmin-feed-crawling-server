import re
from datetime import datetime
from bs4 import BeautifulSoup
from template.notice_data import NoticeData
from utils.scraper_type import ScraperType
from utils.web_scraper import WebScraper
from config.logger_config import setup_logger

logger = setup_logger(__name__)


class SciencetechnologySecurityAcademicScraper(WebScraper):
    """정보보안암호수학과 학사공지 스크래퍼"""

    def __init__(self, url: str):
        super().__init__(url, ScraperType.SCIENCETECHNOLOGY_SECURITY_ACADEMIC)

    def get_list_elements(self, soup: BeautifulSoup) -> list:
        """공지사항 목록을 가져옵니다."""
        # 모든 공지사항 (일반 공지 + 상단 고정 공지)
        notice_list = soup.select("tbody tr")
        return notice_list

    async def parse_notice_from_element(self, element) -> NoticeData:
        """개별 공지사항 정보를 파싱합니다."""
        try:
            # 공지사항 여부 확인
            is_notice = False
            num_box = element.select_one(".b-num-box")
            if (
                num_box
                and num_box.select_one("span")
                and "공지" in num_box.select_one("span").text
            ):
                is_notice = True

            title_element = element.select_one(".b-title-box a")

            title = title_element.text.strip() if title_element else "제목 없음"
            # 공지사항인 경우 제목 앞에 [공지] 표시 추가
            if is_notice and not title.startswith("[공지]"):
                title = f"[공지] {title}"

            # 링크 생성 (상대 경로인 경우 기본 URL과 결합)
            link = title_element.get("href", "") if title_element else ""
            if link and link.startswith("?"):
                base_url = self.url.split("?")[0]
                link = f"{base_url}{link}"

            # 날짜 정보 추출
            date_element = element.select_one(".b-date")
            date_text = date_element.text.strip() if date_element else ""

            # 날짜 포맷 변환 (YY.MM.DD → YYYY-MM-DD)
            if date_text:
                date_match = re.search(r"(\d{2})\.(\d{2})\.(\d{2})", date_text)
                if date_match:
                    year, month, day = date_match.groups()
                    year = "20" + year  # 2000년대로 가정
                    published = datetime.strptime(f"{year}-{month}-{day}", "%Y-%m-%d")
                else:
                    published = datetime.now()
            else:
                published = datetime.now()

            # 로깅
            logger.debug(f"파싱된 공지사항: {title}")
            if is_notice:
                logger.debug(f"상단 고정 공지 파싱: {title}")

            return NoticeData(title, link, published, self.scraper_type)

        except Exception as e:
            logger.error(f"공지사항 파싱 중 오류: {e}")
            return None
