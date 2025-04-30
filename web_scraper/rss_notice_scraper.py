import feedparser
from datetime import datetime
from template.notice_data import NoticeData
from utils.scraper_type import ScraperType
from config.db_config import read_notice_list
from utils.web_scraper import WebScraper
from bs4 import BeautifulSoup
from config.logger_config import setup_logger


class RSSNoticeScraper(WebScraper):
    """RSS 피드 스크래퍼"""

    def __init__(self, url: str, scraper_type: ScraperType):
        """RSS 피드 스크래퍼를 초기화합니다.

        Args:
            url (str): RSS 피드 URL
            scraper_type (ScraperType, optional): 스크래퍼 타입. 기본값은 SWACADEMIC
        """
        super().__init__(url, scraper_type)
        self.logger = setup_logger(self.scraper_type.get_collection_name())

    def parse_date(self, date_str):
        """날짜 문자열을 datetime 객체로 변환합니다."""
        try:
            dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
            return dt
        except Exception as e:
            self.logger.error(f"날짜 파싱 오류: {e}")
            return datetime.now(self.kst)

    def get_list_elements(self, soup: BeautifulSoup) -> list:
        """RSS 피드에서는 사용하지 않습니다."""
        return []

    async def parse_notice_from_element(self, element) -> NoticeData:
        """RSS 피드에서는 사용하지 않습니다."""
        return None

    async def check_updates(self) -> list:
        """RSS 피드를 확인하여 새로운 글이 있으면 반환합니다."""
        try:
            # DB에서 해당 스크래퍼 타입의 최신 공지사항 가져오기
            recent_notices = read_notice_list(notice_type=self.scraper_type.get_collection_name())

            # 링크와 제목으로 비교하기 위한 set
            recent_links = {notice["link"] for notice in recent_notices}
            recent_titles = {notice["title"] for notice in recent_notices}

            # RSS 피드 파싱
            feed = feedparser.parse(self.url)
            new_notices = []

            for entry in feed.entries[:20]:  # 최근 20개만 가져오기
                notice = NoticeData(
                    title=entry.title,
                    link=entry.link,
                    published=self.parse_date(entry.published),
                    scraper_type=self.scraper_type,
                )

                self.logger.debug(f"[크롤링된 공지] {notice.title}")

                if notice.link in recent_links or notice.title in recent_titles:
                    self.logger.debug("=> 이미 등록된 공지사항입니다")
                else:
                    self.logger.debug("=> 새로운 공지사항입니다!")
                    new_notices.append(notice)

            self.logger.info(f"총 {len(new_notices)}개의 새로운 공지사항")
            return new_notices

        except Exception as e:
            self.logger.error(f"RSS 피드 확인 중 오류 발생: {e}")
            return []
