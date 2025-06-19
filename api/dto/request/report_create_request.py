from dataclasses import dataclass

@dataclass
class DailyReportCreateRequest:
    """
    API 리포트 생성 요청을 위한 데이터 클래스(DTO)
    """
    user_id: int
    date: str
    report: dict  # 실제 보고서 내용은 딕셔너리 형태로 유지

    def to_payload(self):
        return {
            "userId": self.user_id,
            "date": self.date,
            "report": self.report
        }

@dataclass
class WeeklyReportCreateRequest:
    """
    API 주간 리포트 생성 요청을 위한 데이터 클래스(DTO)
    """
    team_id: int
    start_date: str
    end_date: str
    report: dict
    
    def to_payload(self):  
        return {
            "teamId": self.team_id,
            "startDate": self.start_date,
            "endDate": self.end_date,
            "report": self.report
        }

@dataclass
class TeamWeeklyReportCreateRequest:
    """
    API 주간 리포트 생성 요청을 위한 데이터 클래스(DTO)
    """
    team_id: int
    start_date: str
    end_date: str
    report: dict
    
    def to_payload(self):  
        return {
            "teamId": self.team_id,
            "startDate": self.start_date,
            "endDate": self.end_date,
            "report": self.report
        }