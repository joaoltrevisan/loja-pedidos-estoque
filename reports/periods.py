from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError

REPORT_TIMEZONE = "America/Sao_Paulo"
REPORT_TZ = ZoneInfo(REPORT_TIMEZONE)
MAX_PERIOD_DAYS = 366


@dataclass(frozen=True)
class ReportPeriod:
    start: date
    end: date

    def __post_init__(self):
        if type(self.start) is not date or type(self.end) is not date:
            raise ValidationError({"period": ["Informe datas de calendario, sem horario."]})
        days = (self.end - self.start).days
        if not 1 <= days <= MAX_PERIOD_DAYS:
            raise ValidationError(
                {"end": ["O periodo deve conter de 1 a 366 dias, com fim exclusivo."]}
            )

    @property
    def bounds(self):
        return tuple(
            datetime.combine(day, time.min, tzinfo=REPORT_TZ).astimezone(UTC)
            for day in (self.start, self.end)
        )

    @property
    def metadata(self):
        return {"start": self.start, "end": self.end, "timezone": REPORT_TIMEZONE}
