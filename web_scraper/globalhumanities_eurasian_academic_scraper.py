from bs4 import BeautifulSoup
from datetime import datetime
from template.notice_data import NoticeData
from utils.scraper_type import ScraperType
from utils.web_scraper import WebScraper
from config.logger_config import setup_logger

logger = setup_logger(__name__)


class GlobalhumanitiesEurasianAcademicScraper(WebScraper):
    """러시아유라시아학과 학사공지 스크래퍼"""

    def __init__(self, url: str):
        super().__init__(url, ScraperType.GLOBALHUMANITIES_EURASIAN_ACADEMIC)
        self.base_url = "https://cms.kookmin.ac.kr"

    def get_list_elements(self, soup: BeautifulSoup) -> list:
        """러시아유라시아학과 학사공지 목록의 HTML 요소들을 가져옵니다."""
        # 고정 공지와 일반 공지 모두 가져오기
        elements = []

        # 상단 고정 공지 가져오기
        top_notices = soup.select("tr.b-top-box")
        if top_notices:
            elements.extend(top_notices)
            self.logger.debug(
                f"총 {len(top_notices)}개의 고정 공지사항 요소를 찾았습니다"
            )

        # 일반 공지 가져오기
        normal_notices = soup.select("table.board-table > tbody > tr:not(.b-top-box)")
        if normal_notices:
            elements.extend(normal_notices)
            self.logger.debug(
                f"총 {len(normal_notices)}개의 일반 공지사항 요소를 찾았습니다"
            )

        self.logger.debug(f"총 {len(elements)}개의 공지사항 요소를 찾았습니다")
        return elements

    async def parse_notice_from_element(self, element) -> NoticeData:
        """HTML 요소에서 러시아유라시아학과 학사공지 정보를 추출합니다."""
        try:
            # 고정 공지 여부 확인
            is_notice = "b-top-box" in element.get("class", [])

            # 일반 공지에서 공지 표시 확인
            if not is_notice:
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
