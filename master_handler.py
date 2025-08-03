import json
import boto3


def handler(event, context):
    """
    Master Lambda Handler
    EventBridge에서 호출되어 scraper로 끝나는 모든 Lambda 함수를 비동기로 실행하는 진입점
    """

    try:
        # Lambda 클라이언트 생성
        lambda_client = boto3.client("lambda")

        # 모든 Lambda 함수 목록 가져오기
        response = lambda_client.list_functions()
        all_functions = response["Functions"]

        # 추가 페이지가 있는 경우 계속 가져오기
        while "NextMarker" in response:
            response = lambda_client.list_functions(Marker=response["NextMarker"])
            all_functions.extend(response["Functions"])

        # scraper로 끝나는 함수들만 필터링
        scraper_functions = [
            func["FunctionName"]
            for func in all_functions
            if func["FunctionName"].endswith("scraper")
        ]

        success_count = 0
        error_count = 0

        # 모든 스크래퍼 함수를 비동기로 호출
        for function_name in scraper_functions:
            try:
                # 개별 스크래퍼 Lambda 함수 비동기 호출
                lambda_client.invoke(
                    FunctionName=function_name,
                    InvocationType="Event",  # 비동기 호출
                    Payload=json.dumps({}),
                )

                success_count += 1

            except Exception as e:
                error_count += 1

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "모든 스크래퍼 Lambda 함수를 비동기로 호출했습니다",
                    "total_scrapers": len(scraper_functions),
                    "invoked_successfully": success_count,
                    "invocation_failed": error_count,
                    "scraper_functions": scraper_functions,
                },
                ensure_ascii=False,
            ),
        }

    except Exception as e:
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
