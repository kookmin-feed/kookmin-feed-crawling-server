import re
from datetime import datetime
from bs4 import BeautifulSoup
from template.notice_data import NoticeData
from utils.scraper_type import ScraperType
from utils.web_scraper import WebScraper
from config.logger_config import setup_logger

logger = setup_logger(__name__)


class SocialscienceCommunicationMediaAcademicScraper(WebScraper):
    """미디어전공 학사공지 스크래퍼"""

    def __init__(self, url: str):
        super().__init__(url, ScraperType.SOCIALSCIENCE_COMMUNICATION_MEDIA_ACADEMIC)

    def get_list_elements(self, soup: BeautifulSoup) -> list:
        """공지사항 목록을 가져옵니다."""
        notice_list = soup.select("tbody tr")
        return notice_list

    async def parse_notice_from_element(self, element) -> NoticeData:
        """개별 공지사항 정보를 파싱합니다."""
        try:
            # 상단 고정 공지 여부 확인
            notice_box = element.select_one(".b-num-box")
            is_top_notice = notice_box and "num-notice" in notice_box.get("class", [])

            # 제목과 링크 추출
            title_element = element.select_one(".b-title-box a")
            if not title_element:
                logger.warning("제목 요소를 찾을 수 없습니다.")
                return None

            # 제목 텍스트 정리 - 불필요한 공백과 줄바꿈 제거
            title = title_element.get_text(strip=True)
            # 추가 정리: 연속된 공백을 하나로 치환
            title = re.sub(r"\s+", " ", title).strip()

            # "자세히 보기" 텍스트 제거
            title = re.sub(r" 자세히 보기$", "", title)

            # 만약 제목이 "..."로 끝나면 원본 title 속성 확인
            if title.endswith("..."):
                # title 속성에서 완전한 제목을 가져오려고 시도
                full_title = title_element.get("title", "")
                if full_title and "자세히 보기" in full_title:
                    # title 속성에서 "자세히 보기" 부분 제거
                    title = re.sub(r" 자세히 보기$", "", full_title)

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
                # YY.MM.DD 형식 파싱 (예: 25.02.20)
                date_match = re.search(r"(\d{2})\.(\d{2})\.(\d{2})", date_text)
                if date_match:
                    year, month, day = date_match.groups()
                    # 20년대로 가정
                    year = "20" + year
                    published = datetime.strptime(f"{year}-{month}-{day}", "%Y-%m-%d")
                else:
                    logger.warning(f"날짜 형식 변환 실패: {date_text}")
                    published = datetime.now()

            # 첨부 파일 여부 확인
            has_attachment = bool(element.select_one(".b-file"))
            if has_attachment:
                logger.debug(f"첨부 파일이 있는 공지: {title}")

            # 로깅
            if is_top_notice:
                logger.debug(f"상단 고정 공지 파싱: {title}")
            else:
                logger.debug(f"일반 공지 파싱: {title}")

            return NoticeData(title, link, published, self.scraper_type)

        except Exception as e:
            logger.error(f"공지사항 파싱 중 오류: {e}")
            return None
