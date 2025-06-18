from dataclasses import dataclass


@dataclass
class DailyReportFetchRequest:
    user_id: int
    start_date: str
    end_date: str
    
    def to_payload(self):
        return {
            "userId": self.user_id,
            "startDate": self.start_date,
            "endDate": self.end_date
        }