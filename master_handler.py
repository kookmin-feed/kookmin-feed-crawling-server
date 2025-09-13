import json
import boto3
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from master_utils import (
    send_master_handler_error_notification,
    load_scraper_types,
    load_scraper_categories,
    save_scraper_categories_to_db,
    save_scraper_types_to_db,
    find_category_by_scraper_type,
)

BATCH_SIZE = 10
MAX_WORKERS = 10


def handler(event, context):
    """
    Master Lambda Handler
    EventBridge에서 호출되어 유효한 스크래퍼 Lambda 함수들을 비동기로 실행하는 진입점
    """

    try:
        # 현재 stage 정보 가져오기
        current_stage = os.environ.get("STAGE", "dev")
        print(f"🚀 [MASTER] Master Handler 시작 (Stage: {current_stage})")

        # 1. 스크래퍼 검증 및 메타데이터 저장
        validation_result = validate_and_save_scrapers()
        if not validation_result["success"]:
            return validation_result["response"]

        valid_scrapers = validation_result["valid_scrapers"]
        scraper_functions = validation_result["scraper_functions"]

        # 2. 유효한 스크래퍼 함수들 호출
        invocation_result = invoke_scrapers(valid_scrapers)

        # 3. 결과 반환
        result = {
            "message": "Master Lambda Handler 실행 완료",
            "validation": {
                "total_found": len(scraper_functions),
                "valid_scrapers": len(valid_scrapers),
                "invalid_scrapers": len(scraper_functions) - len(valid_scrapers),
                "valid_scraper_functions": valid_scrapers,
            },
            "invocation": invocation_result,
        }

        print(
            f"🎉 [MASTER] 실행 완료 - 성공: {invocation_result['invoked_successfully']}, 실패: {invocation_result['invocation_failed']}"
        )
        return {
            "statusCode": 200,
            "body": json.dumps(result, ensure_ascii=False, default=str),
        }

    except Exception as e:
        error_msg = f"Master Handler 실행 중 오류: {str(e)}"
        print(f"❌ [MASTER] {error_msg}")
        send_master_handler_error_notification("handler", error_msg)
        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "error": "Master Lambda Handler 실행 중 오류가 발생했습니다.",
                    "details": str(e),
                },
                ensure_ascii=False,
            ),
        }


def validate_and_save_scrapers():
    """스크래퍼 검증 및 메타데이터 저장을 수행합니다."""

    # 현재 stage 정보 가져오기
    current_stage = os.environ.get("STAGE", "dev")

    # 1. JSON 파일들 로드
    print(f"📋 [MASTER] 스크래퍼 설정 파일 로드 (Stage: {current_stage})")
    scraper_types = load_scraper_types()
    scraper_categories = load_scraper_categories()

    if not scraper_types or not scraper_categories:
        print("❌ [MASTER] 스크래퍼 설정 파일 로드 실패")
        return {
            "success": False,
            "response": {
                "statusCode": 500,
                "body": json.dumps(
                    {"error": "스크래퍼 설정 파일을 로드할 수 없습니다."},
                    ensure_ascii=False,
                ),
            },
        }

    print(f"📊 [MASTER] 로드된 스크래퍼 타입: {len(scraper_types)}개")
    print(f"📊 [MASTER] 로드된 스크래퍼 카테고리: {len(scraper_categories)}개")

    # 2. Lambda 함수 목록 가져오기
    print("🔍 [MASTER] Lambda 함수 목록 조회")
    lambda_client = boto3.client("lambda")
    response = lambda_client.list_functions()
    all_functions = response["Functions"]

    # 추가 페이지가 있는 경우 계속 가져오기
    while "NextMarker" in response:
        response = lambda_client.list_functions(Marker=response["NextMarker"])
        all_functions.extend(response["Functions"])

    # 3. 현재 stage에 해당하는 scraper 함수들만 필터링
    scraper_functions = [
        func["FunctionName"]
        for func in all_functions
        if func["FunctionName"].endswith("scraper")
        and func["FunctionName"].startswith(f"{current_stage}-")
    ]

    print(
        f"📋 [MASTER] 발견된 스크래퍼 Lambda 함수 ({current_stage}): {len(scraper_functions)}개"
    )

    # 4. 유효한 스크래퍼 함수들 필터링
    valid_scrapers = validate_scrapers(
        scraper_functions, scraper_types, scraper_categories
    )

    print(f"✅ [MASTER] 유효한 스크래퍼: {len(valid_scrapers)}개")
    print(
        f"❌ [MASTER] 유효하지 않은 스크래퍼: {len(scraper_functions) - len(valid_scrapers)}개"
    )

    # 5. 유효한 스크래퍼 정보를 DB에 저장
    print("💾 [MASTER] 스크래퍼 메타데이터 DB 저장 시작")
    save_scraper_categories_to_db(scraper_categories)
    save_scraper_types_to_db(scraper_types, valid_scrapers)
    print("💾 [MASTER] 스크래퍼 메타데이터 DB 저장 완료")

    return {
        "success": True,
        "valid_scrapers": valid_scrapers,
        "scraper_functions": scraper_functions,
    }


def invoke_scrapers(valid_scrapers):
    """유효한 스크래퍼 함수들을 10개씩 배치로 병렬 호출합니다."""

    success_count = 0
    error_count = 0
    invocation_results = []

    print(f"🚀 [MASTER] {len(valid_scrapers)}개 스크래퍼를 10개씩 배치로 병렬 실행")

    start_time = time.time()

    def call_single_lambda(function_name):
        try:
            lambda_client = boto3.client("lambda")
            lambda_client.invoke(
                FunctionName=function_name,
                InvocationType="Event",
                Payload=json.dumps({}),
            )
            print(f"   ✅ {function_name} 호출 완료")
            return {
                "function_name": function_name,
                "status": "success",
                "message": "호출 성공",
            }
        except Exception as e:
            return {
                "function_name": function_name,
                "status": "error",
                "message": str(e),
            }

    # 45개를 10개씩 나누기
    batches = [valid_scrapers[i : i + 10] for i in range(0, len(valid_scrapers), 10)]

    for batch_index, batch in enumerate(batches, 1):
        print(f"🔄 [배치 {batch_index}] {len(batch)}개 스크래퍼 병렬 실행")
        print(f"   📋 실행 목록: {', '.join(batch)}")

        # 현재 배치를 병렬로 실행
        with ThreadPoolExecutor(max_workers=10) as executor:
            batch_results = list(executor.map(call_single_lambda, batch))

        # 결과 집계
        for result in batch_results:
            if result["status"] == "success":
                success_count += 1
            else:
                error_count += 1
            invocation_results.append(result)

        end_time = time.time()
        exec_time = end_time - start_time

        print(f"✅ [배치 {batch_index}] 완료")
        print(f"⏱️ [MASTER] 스크래퍼 호출 실행 시간: {exec_time:.4f}초")

    return {
        "total_scrapers": len(valid_scrapers),
        "invoked_successfully": success_count,
        "invocation_failed": error_count,
        "invocation_results": invocation_results,
    }


def validate_scrapers(scraper_functions, scraper_types, scraper_categories):
    """
    스크래퍼 Lambda 함수들이 유효한지 검증합니다.

    Args:
        scraper_functions: Lambda 함수 이름 리스트
        scraper_types: 스크래퍼 타입 정보
        scraper_categories: 스크래퍼 카테고리 정보

    Returns:
        List[str]: 유효한 스크래퍼 Lambda 함수 이름 리스트
    """
    current_stage = os.environ.get("STAGE", "dev")
    valid_scrapers = []

    # JSON에 정의된 스크래퍼 타입들을 순회하면서 해당하는 Lambda 함수가 존재하는지 확인
    for scraper_type, scraper_info in scraper_types.items():
        # 1. 스크래퍼 타입이 어떤 카테고리에 속하는지 확인
        category = find_category_by_scraper_type(scraper_type, scraper_categories)
        if not category:
            print(
                f"❌ [VALIDATE] 카테고리를 찾을 수 없는 스크래퍼 타입: {scraper_type}"
            )
            continue

        # 3. JSON의 scraper_lambda_function_name에 stage prefix를 추가하여 실제 Lambda 함수명과 비교
        base_function_name = scraper_info.get("scraper_lambda_function_name")
        if not base_function_name:
            print(
                f"❌ [VALIDATE] Lambda 함수명이 정의되지 않은 스크래퍼 타입: {scraper_type}"
            )
            continue

        # stage prefix를 추가한 실제 함수명 생성
        expected_function_name = f"{current_stage}-{base_function_name}"

        # 실제 Lambda 함수 이름 확인
        if expected_function_name not in scraper_functions:
            print(
                f"❌ [VALIDATE] Lambda 함수가 존재하지 않는 스크래퍼 타입: {scraper_type} (예상: {expected_function_name}, 기본: {base_function_name})"
            )
            continue

        matching_function = expected_function_name

        print(
            f"✅ [VALIDATE] 유효한 스크래퍼 ({current_stage}): {matching_function} ({scraper_type} -> {category})"
        )
        valid_scrapers.append(matching_function)

    return valid_scrapers
