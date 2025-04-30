import asyncio
import sys
import pytz
from datetime import datetime
from utils.scraper_type import ScraperType
from config.logger_config import setup_logger
from config.db_config import get_database, close_database, save_notice
from utils.scraper_factory import ScraperFactory
from config.env_loader import ENV
from utils.check_new_scraper import run_check_new_scraper

if ENV["IS_PROD"]:
    INTERVAL = 10
else:
    INTERVAL = 2

print(f"INTERVAL: {INTERVAL}")

async def process_new_notices(notices, scraper_type: ScraperType):
    """새로운 공지사항을 처리합니다."""
    for notice in notices:
        # DB에 저장
        await save_notice(notice, scraper_type)

def is_working_hour():
    """현재 시간이 작동 시간(월~토 8시~20시)인지 확인합니다."""
    if not ENV["IS_PROD"]:
        return True

    now = datetime.now(pytz.timezone("Asia/Seoul"))

    # 일요일(6) 체크
    if now.weekday() == 6:
        return False

    # 시간 체크 (8시~20시)
    if now.hour < 8 or now.hour >= 21:
        return False

    return True


async def check_all_notices():
    """모든 스크래퍼를 실행하고 새로운 공지사항을 처리합니다."""
    while True:
        try:
            # 작동 시간이 아니면 스킵
            if not is_working_hour():
                current_time = datetime.now(pytz.timezone("Asia/Seoul")).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                logger.info(f"작동 시간이 아닙니다. (현재 시각: {current_time})")
            else:
                # 활성화된 모든 스크래퍼 실행
                for scraper_type in ScraperType.get_active_scrapers():
                    try:
                        # 스크래퍼 생성
                        scraper = ScraperFactory().create_scraper(scraper_type)
                        if not scraper:
                            logger.error(f"지원하지 않는 스크래퍼 타입: {scraper_type.name}")
                            continue

                        # 공지사항 확인 및 처리
                        notices = await scraper.check_updates()
                        await process_new_notices(notices, scraper_type)

                    except Exception as e:
                        logger.error(
                            f"{scraper_type.get_korean_name()} 스크래핑 중 오류 발생: {e}")
                        continue

        except Exception as e:
            logger.error(f"스크래핑 작업 중 오류 발생: {e}")

        # INTERVAL 간격으로 대기
        await asyncio.sleep(INTERVAL * 60)


async def main():
    logger.info("스크래퍼 서버를 시작합니다...")

    try:
        # MongoDB 연결 초기화
        db = get_database()
        logger.info("MongoDB 연결이 성공적으로 설정되었습니다.")

        # 새로운 스크롤러 확인 실행
        await run_check_new_scraper()

        # 크롤링 태스크 시작
        check_all_notices_task = asyncio.create_task(check_all_notices())
        logger.info("크롤링 작업이 시작되었습니다.")

        # 두 작업을 병렬로 실행
        await asyncio.gather(check_all_notices_task)

    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("\n프로그램을 종료합니다...")
    except Exception as e:
        logger.error(f"오류 발생: {e}")
    finally:
        # 태스크 취소
        check_all_notices_task.cancel()
        await check_all_notices_task  # 태스크가 안전하게 종료되도록 대기
        close_database()
        await asyncio.get_event_loop().shutdown_asyncgens()

if __name__ == "__main__":
    logger = setup_logger(__name__)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("프로그램이 안전하게 종료되었습니다.")
