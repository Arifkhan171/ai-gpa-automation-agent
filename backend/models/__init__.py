# AcadTrack backend models — import here so SQLAlchemy registers all tables
from backend.models.user_model import User  # noqa: F401
from backend.models.upload_model import UploadJob  # noqa: F401
from backend.models.transcript_model import TranscriptRecord  # noqa: F401
from backend.models.payment_model import PaymentVoucher  # noqa: F401
