from bs4 import BeautifulSoup
from datetime import datetime
from template.notice_data import NoticeData
from utils.scraper_type import ScraperType
from utils.web_scraper import WebScraper
from config.logger_config import setup_logger

logger = setup_logger(__name__)


class ArtsAcademicScraper(WebScraper):
    """예술대학 학사공지 스크래퍼"""

    def __init__(self, url: str):
        super().__init__(url, ScraperType.ARTS_ACADEMIC)
        self.base_url = "https://art.kookmin.ac.kr"

    def get_list_elements(self, soup: BeautifulSoup) -> list:
        """예술대학 학사공지 목록의 HTML 요소들을 가져옵니다."""
        # div.list-tbody 내의 모든 ul 요소 선택
        elements = soup.select("div.list-tbody > ul")
        self.logger.debug(f"총 {len(elements)}개의 공지사항 요소를 찾았습니다")
        return elements if elements else []

    async def parse_notice_from_element(self, element) -> NoticeData:
        """HTML 요소에서 예술대학 학사공지 정보를 추출합니다."""
        try:
            # 공지사항 여부 확인
            is_notice = element.select_one("li.notice") is not None

            # 제목과 링크 추출
            subject_li = element.select_one("li.subject")
            if not subject_li:
                return None

            a_tag = subject_li.select_one("a")
            if not a_tag:
                return None

            title = a_tag.text.strip()
            relative_link = a_tag.get("href", "")

            # 상대 경로를 절대 경로로 변환
            if relative_link.startswith("./"):
                link = f"{self.url}{relative_link[1:]}"
            elif relative_link.startswith("/"):
                link = f"{self.base_url}{relative_link}"
            else:
                link = f"{self.url}{relative_link}"

            # 날짜 추출
            date_li = element.select_one("li.date")
            if not date_li:
                self.logger.warning("날짜 요소를 찾을 수 없음")
                published = datetime.now(self.kst)
            else:
                date_str = date_li.text.strip()
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
                        self.logger.error(f"날짜 파싱 오류: {date_str}")
                        published = datetime.now(self.kst)

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
            self.logger.error(f"공지사항 파싱 중 오류: {e}")
            return None
