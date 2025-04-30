from bs4 import BeautifulSoup
from datetime import datetime
from template.notice_data import NoticeData
from utils.scraper_type import ScraperType
from utils.web_scraper import WebScraper
from config.logger_config import setup_logger

logger = setup_logger(__name__)


class UniversitySpeciallectureScraper(WebScraper):
    """대학 특강공지 스크래퍼"""

    def __init__(self, url: str):
        super().__init__(url, ScraperType.UNIVERSITY_SPECIALLECTURE)

    def get_list_elements(self, soup: BeautifulSoup) -> list:
        """특강공지 목록의 HTML 요소들을 가져옵니다."""
        # notice-bg(공지사항)와 normal-bg(일반 게시물) 모두 가져옴
        elements = soup.select(".list-tbody .normal-bg, .list-tbody .notice-bg")
        return elements if elements else []

    async def parse_notice_from_element(self, element) -> NoticeData:
        """HTML 요소에서 특강공지 정보를 추출합니다."""
        try:
            # 공지사항 여부 확인
            is_notice = "notice-bg" in element.get("class", [])

            # 제목과 링크 추출
            title_tag = element.select_one(".subject a")
            if not title_tag:
                return None

            title = title_tag.text.strip()
            link = title_tag["href"]
            if not link.startswith("http"):
                link = f"https://cs.kookmin.ac.kr/news/kookmin/special_lecture/{link}"

            # 날짜 추출
            date = element.select_one(".date").text.strip()
            published = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=self.kst)

            # 공지사항인 경우 제목 앞에 [공지] 표시 추가
            if is_notice and not title.startswith("[공지]"):
                title = f"[공지] {title}"

            return NoticeData(
                title=title,
                link=link,
                published=published,
                scraper_type=self.scraper_type,
            )
        except Exception as e:
            logger.error(f"공지사항 파싱 중 오류: {e}")
            return None
