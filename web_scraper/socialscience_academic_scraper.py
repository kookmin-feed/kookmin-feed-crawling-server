from bs4 import BeautifulSoup
from datetime import datetime
from template.notice_data import NoticeData
from utils.scraper_type import ScraperType
from utils.web_scraper import WebScraper
from config.logger_config import setup_logger

logger = setup_logger(__name__)


class SocialscienceAcademicScraper(WebScraper):
    """사회과학대학 학사공지 스크래퍼"""

    def __init__(self, url: str):
        super().__init__(url, ScraperType.SOCIALSCIENCE_ACADEMIC)
        self.base_url = "https://social.kookmin.ac.kr"

    def get_list_elements(self, soup: BeautifulSoup) -> list:
        """사회과학대학 학사공지 목록의 HTML 요소들을 가져옵니다."""
        # 테이블의 모든 행을 가져오지만 헤더 행은 제외
        table = soup.select_one("table.board-table")
        if not table:
            self.logger.error("테이블을 찾을 수 없습니다")
            return []

        # tbody에서 모든 tr 요소 선택
        elements = table.select("tbody tr")
        self.logger.debug(f"총 {len(elements)}개의 공지사항 요소를 찾았습니다")
        return elements if elements else []

    async def parse_notice_from_element(self, element) -> NoticeData:
        """HTML 요소에서 사회과학대학 학사공지 정보를 추출합니다."""
        try:
            # 공지사항 여부 확인 (고정 공지가 없더라도, 이후 추가될 경우를 대비해 코드 유지)
            notice_td = element.select_one("td.b-num-box.num-notice")
            is_notice = notice_td is not None

            # 제목과 링크 추출
            title_td = element.select_one("td.b-td-left")
            if not title_td:
                return None

            title_box = title_td.select_one("div.b-title-box")
            if not title_box:
                return None

            a_tag = title_box.select_one("a")
            if not a_tag:
                return None

            # title 속성에서 제목 추출 (자세히 보기 텍스트 제거)
            title_attr = a_tag.get("title", "")
            if title_attr:
                title = title_attr.replace(" 자세히 보기", "").strip()
            else:
                # title 속성이 없으면 텍스트 콘텐츠 사용
                title = a_tag.text.strip()

            relative_link = a_tag.get("href", "")

            # URL 파라미터 형식 확인 및 절대 경로 생성
            if relative_link.startswith("?"):
                link = f"{self.url}{relative_link}"
            elif relative_link.startswith("/"):
                link = f"{self.base_url}{relative_link}"
            else:
                link = f"{self.base_url}/{relative_link}"

            # 날짜 추출 - b-date 클래스 내의 텍스트 사용
            date_span = element.select_one("span.b-date")
            if not date_span:
                # 테이블의 날짜 셀에서 시도
                date_td = element.select_one(
                    "td:nth-child(4)"
                )  # 4번째 셀이 날짜인 경우
                if date_td and date_td.text.strip():
                    date_str = date_td.text.strip()
                else:
                    self.logger.warning("날짜 요소를 찾을 수 없음")
                    published = datetime.now(self.kst)
                    return NoticeData(
                        title=title,
                        link=link,
                        published=published,
                        scraper_type=self.scraper_type,
                    )
            else:
                date_str = date_span.text.strip()

            try:
                # YYYY-MM-DD 형식 (예: 2022-03-11)
                published = datetime.strptime(date_str, "%Y-%m-%d").replace(
                    tzinfo=self.kst
                )
            except ValueError:
                try:
                    # YYYY.MM.DD 형식
                    published = datetime.strptime(date_str, "%Y.%m.%d").replace(
                        tzinfo=self.kst
                    )
                except ValueError:
                    try:
                        # YY.MM.DD 형식 (예: 22.03.11)
                        published = datetime.strptime(date_str, "%y.%m.%d").replace(
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
