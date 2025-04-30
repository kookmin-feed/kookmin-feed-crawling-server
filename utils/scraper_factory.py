from typing import Optional, Dict, Type
import os
import importlib
from utils.scraper_type import ScraperType
from utils.web_scraper import WebScraper
from web_scraper.rss_notice_scraper import RSSNoticeScraper
import sys
from pathlib import Path
from config.logger_config import setup_logger

# 로거 설정
logger = setup_logger(__name__)


class ScraperFactory:
    """스크래퍼 객체를 생성하는 팩토리 클래스"""

    _instance = None
    _scraper_classes: Dict[str, Type[WebScraper]] = {}

    @classmethod
    def _initialize_scraper_classes(cls):
        """web_scraper 폴더의 모든 스크래퍼 클래스를 동적으로 import하여 초기화합니다."""
        logger.info("=" * 65)
        logger.info("▶ 스크래퍼 팩토리 초기화 시작")
        logger.info("=" * 65)

        # RSS 스크래퍼 추가 (utils 폴더에 있음)
        cls._scraper_classes["RSSNoticeScraper"] = RSSNoticeScraper
        logger.info(f"RSSNoticeScraper 클래스가 추가되었습니다.")

        # web_scraper 폴더 경로 설정
        current_dir = Path(__file__).parent.parent
        scraper_dir = current_dir / "web_scraper"

        # Python path에 web_scraper 폴더 추가
        sys.path.append(str(current_dir))

        try:
            # web_scraper 폴더의 모든 .py 파일을 검사
            for filename in os.listdir(scraper_dir):
                if filename.endswith("_scraper.py") and not filename.startswith("__"):
                    # 파일 이름에서 .py 확장자 제거
                    module_name = filename[:-3]

                    try:
                        # 모듈 import
                        module = importlib.import_module(f"web_scraper.{module_name}")

                        # rss가 포함된 모듈은 이미 처리되었으므로 건너뜀
                        if "rss" in module_name.lower():
                            logger.info(
                                f"RSS 모듈은 별도로 처리되었으므로 건너뜁니다: {module_name}"
                            )
                            continue

                        # snake_case를 CamelCase로 변환
                        class_name = "".join(
                            word.capitalize() for word in module_name.split("_")
                        )

                        logger.debug(
                            f"모듈: {module_name} -> 클래스: {class_name} 변환 시도"
                        )

                        # 해당 클래스가 모듈에 존재하는지 확인하고 추가
                        if hasattr(module, class_name):
                            cls._scraper_classes[class_name] = getattr(
                                module, class_name
                            )
                            logger.info(f"스크래퍼 클래스 로드 성공: {class_name}")
                        else:
                            logger.error(
                                f"Class {class_name} not found in module {module_name}"
                            )

                    except Exception as e:
                        logger.error(f"모듈 임포트 오류 ({module_name}): {e}")

        except Exception as e:
            logger.error(f"web_scraper 디렉토리 스캔 중 오류 발생: {e}")

        logger.info(
            f"총 {len(cls._scraper_classes)}개의 스크래퍼 클래스가 로드되었습니다."
        )
        logger.info("=" * 65)
        logger.info("✅ 스크래퍼 팩토리 초기화 완료")
        logger.info("=" * 65)

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._initialize_scraper_classes()
        return cls._instance

    def create_scraper(self, scraper_type: ScraperType) -> Optional[WebScraper]:
        """스크래퍼 타입에 맞는 스크래퍼 객체를 생성합니다."""
        url = scraper_type.get_url()
        scraper_class_name = scraper_type.get_scraper_class_name()

        scraper_class = self._scraper_classes.get(scraper_class_name)

        if not scraper_class:
            logger.error(f"스크래퍼 클래스를 찾을 수 없음: {scraper_class_name}")
            return None

        logger.debug(f"스크래퍼 생성: {scraper_class_name} (URL: {url})")

        # RSS 스크래퍼인 경우 scraper_type도 전달
        if scraper_type.name.endswith("_RSS"):
            return scraper_class(url, scraper_type)

        # 일반 스크래퍼인 경우
        return scraper_class(url)
