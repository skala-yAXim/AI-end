import json
from dataclasses import dataclass, asdict

@dataclass
class ReportCreateRequest:
    """
    API 리포트 생성 요청을 위한 데이터 클래스(DTO)
    """
    userId: int
    startDate: str
    endDate: str
    report: dict  # 실제 보고서 내용은 딕셔너리 형태로 유지

    def to_payload(self) -> dict:
        """
        API 서버에 전송할 최종 payload 딕셔너리를 생성합니다.
        'report' 필드는 JSON 형식의 문자열로 변환됩니다.
        """
        # dataclass를 딕셔너리로 변환
        payload_dict = asdict(self)
        # 'report' 딕셔너리를 JSON 문자열로 변환하여 덮어쓰기
        payload_dict['report'] = json.dumps(self.report, ensure_ascii=False)
        return payload_dict