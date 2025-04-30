from __future__ import annotations

from abc import ABC, abstractmethod
import aiohttp
from bs4 import BeautifulSoup
import pytz
from template.notice_data import NoticeData
from config.db_config import read_notice_list
from config.logger_config import setup_logger
from utils.scraper_type import ScraperType
from typing import List


class WebScraper(ABC):
    """웹 스크래퍼 추상 클래스"""

    def __init__(self, url: str, scraper_type: ScraperType):
        self.url = url
        self.scraper_type = scraper_type
        self.kst = pytz.timezone("Asia/Seoul")
        self.logger = setup_logger(self.scraper_type.get_collection_name())

    async def check_updates(self) -> List[NoticeData]:
        """웹페이지를 확인하여 새로운 공지사항이 있으면 반환합니다."""
        try:
            # DB에서 해당 스크래퍼 타입의 최신 공지사항 가져오기
            recent_notices = read_notice_list(notice_type=self.scraper_type.get_collection_name())

            # 링크와 제목으로 비교하기 위한 set
            recent_links = {notice["link"] for notice in recent_notices}
            recent_titles = {notice["title"] for notice in recent_notices}

            # 웹페이지 가져오기 (fetch_page 메서드 사용)
            soup = await self.fetch_page()
            if not soup:
                return []
            elements = self.get_list_elements(soup)

            new_notices = []
            for element in elements:
                notice = await self.parse_notice_from_element(element)
                if notice:
                    self.logger.debug(f"[크롤링된 공지] {notice.title}")

                    if notice.link in recent_links or notice.title in recent_titles:
                        self.logger.debug("=> 이미 등록된 공지사항입니다")
                    else:
                        self.logger.debug("=> 새로운 공지사항입니다!")
                        new_notices.append(notice)

            self.logger.info(f"총 {len(new_notices)}개의 새로운 공지사항")

            return new_notices

        except Exception as e:
            self.logger.error(f"공지사항 확인 중 오류 발생: {e}")
            return []

    @abstractmethod
    async def parse_notice_from_element(self, element) -> NoticeData:
        """HTML 요소에서 공지사항 정보를 추출합니다."""
        pass

    @abstractmethod
    def get_list_elements(self, soup: BeautifulSoup) -> list:
        """공지사항 목록의 HTML 요소들을 가져옵니다."""
        pass

    async def fetch_page(self) -> BeautifulSoup:
        """웹 페이지를 비동기적으로 가져와 BeautifulSoup 객체로 반환합니다."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.url) as response:
                    if response.status != 200:
                        self.logger.error(
                            f"페이지 요청 실패: {self.url}, 상태 코드: {response.status}"
                        )
                        return None

                    html = await response.read()

                    # 인코딩 문제 해결: 먼저 UTF-8로 시도하고, 실패하면 EUC-KR 등으로 시도
                    try:
                        html_text = html.decode("utf-8")
                    except UnicodeDecodeError:
                        try:
                            html_text = html.decode("euc-kr")
                        except UnicodeDecodeError:
                            html_text = html.decode("cp949", errors="replace")

                    return BeautifulSoup(html_text, "html.parser")
        except Exception as e:
            self.logger.error(f"페이지 요청 중 오류: {e}")
            return None
