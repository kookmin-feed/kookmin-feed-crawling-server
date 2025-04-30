from config.logger_config import setup_logger
from config.db_config import get_database, save_notice, save_scraper_type, save_scraper_categories
from utils.scraper_type import ScraperType
from utils.scraper_factory import ScraperFactory

logger = setup_logger(__name__)

async def init_scraper_metadata():
    """
    DB에 스크래퍼 타입과 카테고리를 저장합니다.
    """
    try:
        # ScraperCategory 저장
        save_scraper_categories()
        logger.info("스크래퍼 카테고리 저장 완료")

        # ScraperType 저장
        for scraper_type in ScraperType.get_active_scrapers():
            save_scraper_type(scraper_type)
            logger.info(f"스크래퍼 타입 저장 완료: {scraper_type.name}")
    except Exception as e:
        logger.error(f"스크래퍼 메타데이터 저장 중 오류 발생: {e}")

async def check_new_scraper():
    """
    모든 스크래퍼 타입에 대해 컬렉션을 확인하고,
    컬렉션이 없거나 비어있는 경우 최신 공지사항으로 초기화합니다.
    """
    db = get_database()

    # 모든 스크래퍼 타입에 대해 검사
    for scraper_type in ScraperType.get_active_scrapers():
        collection_name = scraper_type.get_collection_name()
        collection = db[collection_name]

        # 컬렉션이 비어있는지 확인
        if collection.count_documents({}) == 0:
            logger.info(f"비어있는 컬렉션 초기화 시작: {collection_name}")
            try:
                # 스크래퍼 생성
                scraper = ScraperFactory().create_scraper(scraper_type)
                if not scraper:
                    logger.error(f"스크래퍼 생성 실패: {collection_name}")
                    continue

                # 최신 공지사항 가져오기
                notices = await scraper.check_updates()

                # DB에 저장 (db_config의 save_notice 사용)
                for notice in notices:
                    await save_notice(notice, scraper_type)

                logger.info(
                    f"컬렉션 초기화 완료: {collection_name} ({len(notices)}개의 공지사항 저장)"
                )

            except Exception as e:
                logger.error(f"컬렉션 초기화 중 오류 발생 ({collection_name}): {e}")
                continue

async def run_check_new_scraper():
    """초기화 프로세스를 실행합니다."""
    logger.info("=" * 65)
    logger.info("▶ 새로운 스크래퍼 확인 작업이 시작되었습니다.")
    logger.info("=" * 65)

    await check_new_scraper()

    logger.info("=" * 65)
    logger.info("✅ 새로운 스크래퍼 확인 작업이 완료되었습니다.")
    logger.info("=" * 65)

    logger.info("=" * 65)
    logger.info("▶ 카테고리와 스크래퍼 타입 초기화가 시작되었습니다.")
    logger.info("=" * 65)

    await init_scraper_metadata()

    logger.info("=" * 65)
    logger.info("✅ 카테고리와 스크래퍼 타입 초기화 작업이 완료되었습니다.")
    logger.info("=" * 65)
