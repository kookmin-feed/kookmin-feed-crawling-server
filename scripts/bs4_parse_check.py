#!/usr/bin/env python3
"""
BeautifulSoup 파싱 가능 여부를 빠르게 검증하는 임시 스크립트.

사용법 예시:
  python scripts/bs4_parse_check.py https://example.com --selector "title" --timeout 10

필요 패키지:
  - requests
  - beautifulsoup4
  - 선택: lxml (parser로 lxml 사용 시)
"""

from __future__ import annotations

import argparse
import sys
import textwrap
from typing import Dict, Optional


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description=textwrap.dedent(
            """
            지정한 URL을 요청하고 BeautifulSoup으로 파싱해 간단한 정보를 출력합니다.

            - 기본 parser는 html.parser 입니다. (lxml 설치 시 --parser lxml 권장)
            - CSS 선택자를 주면 해당 요소 개수와 예시 텍스트를 출력합니다.
            """
        ).strip(),
    )
    parser.add_argument("url", help="요청할 URL")
    parser.add_argument(
        "--selector",
        default=None,
        help="검증할 CSS 선택자 (예: 'title', 'h1', 'div.article')",
    )
    parser.add_argument(
        "--parser",
        default="html.parser",
        choices=["html.parser", "lxml"],
        help="BeautifulSoup parser 선택 (기본: html.parser)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="요청 타임아웃(초) (기본: 10)",
    )
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=2_000_000,
        help="응답 최대 바이트 수 (기본: 2,000,000)",
    )
    parser.add_argument(
        "--user-agent",
        default=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36"
        ),
        help="요청 User-Agent 문자열",
    )
    parser.add_argument(
        "--verify-ssl",
        action="store_true",
        help="SSL 인증서 검증 활성화 (기본 비활성화)",
    )
    return parser.parse_args()


def fetch(
    url: str, timeout: int, max_bytes: int, headers: Dict[str, str], verify_ssl: bool
) -> bytes:
    try:
        import requests  # type: ignore
    except Exception as exc:  # pragma: no cover
        print(
            "[에러] requests 패키지가 필요합니다. pip install requests", file=sys.stderr
        )
        raise

    with requests.get(
        url, headers=headers, timeout=timeout, stream=True, verify=verify_ssl
    ) as resp:
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        if (
            "text/html" not in content_type
            and "application/xhtml+xml" not in content_type
        ):
            print(f"[경고] 예상과 다른 Content-Type: {content_type}")

        # 바이트 제한만큼만 읽기
        data = bytearray()
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                data.extend(chunk)
                if len(data) > max_bytes:
                    print(f"[정보] 응답을 {max_bytes}바이트에서 절단했습니다.")
                    break
        return bytes(data)


def try_parse(html_bytes: bytes, parser: str, selector: Optional[str]) -> None:
    try:
        from bs4 import BeautifulSoup  # type: ignore
    except Exception:
        print(
            "[에러] beautifulsoup4 패키지가 필요합니다. pip install beautifulsoup4",
            file=sys.stderr,
        )
        raise

    encoding_guess = None
    try:
        # 간단한 인코딩 추측
        encoding_guess = "utf-8"
        html_str = html_bytes.decode(encoding_guess, errors="replace")
    except Exception:
        # 최후 수단
        html_str = html_bytes.decode(errors="replace")

    soup = BeautifulSoup(html_str, parser)

    # 기본 정보
    title_text = soup.title.get_text(strip=True) if soup.title else "(title 없음)"
    print(f"[성공] 파싱 완료 - parser={parser}")
    print(f"[정보] 추정 인코딩: {encoding_guess or 'unknown'}")
    print(f"[정보] 문서 title: {title_text}")
    body = soup.body
    if body is not None:
        sample_text = body.get_text(" ", strip=True)
        print(f"[정보] 본문 텍스트(앞 200자): {sample_text[:200]}")

    # 선택자 테스트
    if selector:
        try:
            matched = soup.select(selector)
            print(f"[검증] selector '{selector}' 결과 개수: {len(matched)}")
            if matched:
                sample = matched[0].get_text(" ", strip=True)
                print(f"[검증] 첫 결과 텍스트(앞 200자): {sample[:200]}")
        except Exception as exc:
            print(f"[에러] 선택자 처리 중 오류: {exc}")


def main() -> int:
    args = parse_args()
    headers = {
        "User-Agent": args.user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    try:
        html_bytes = fetch(
            url=args.url,
            timeout=args.timeout,
            max_bytes=args.max_bytes,
            headers=headers,
            verify_ssl=args.verify_ssl,
        )
    except Exception as exc:
        print(f"[에러] 요청 실패: {exc}", file=sys.stderr)
        return 2

    try:
        try_parse(html_bytes, parser=args.parser, selector=args.selector)
        return 0
    except Exception as exc:
        print(f"[에러] 파싱 실패: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
