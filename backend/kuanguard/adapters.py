"""Explicit provider contracts. Disabled providers cannot claim success or perform network writes."""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ProviderResult:
    status: str
    reference: str | None
    evidence_time: str | None
    simulated: bool = False


class MailAdapter(Protocol):
    def dispatch(self, planned_message_id: str, recipient: str, approved_template_revision: str) -> ProviderResult: ...
    def reconcile(self, provider_reference: str) -> ProviderResult: ...


class GophishAdapter:
    """Legacy source, tenant cells and approved sender credentials are activation prerequisites."""
    capabilities = {"enabled": False, "capture_passwords": False, "tenant_cell_required": True,
                    "browser_admin_key": False, "reason": "authorized existing Gophish source and configuration unavailable"}

    def dispatch(self, *args, **kwargs):
        raise RuntimeError("GOPHISH_NOT_ACTIVATED")

    def reconcile(self, *args, **kwargs):
        raise RuntimeError("GOPHISH_NOT_ACTIVATED")


class DisabledAdapter:
    def __init__(self, capability):
        self.capability = capability

    def execute(self, *args, **kwargs):
        raise RuntimeError(f"{self.capability.upper()}_NOT_ACTIVATED")


def health():
    return [
        {"name": "gophish", "status": "disabled", "detail": "既有授權程式與租戶引擎設定待提供", **GophishAdapter.capabilities},
        {"name": "mail", "status": "disabled", "detail": "通知與演練分流憑證待設定；本機不發信"},
        {"name": "payment", "status": "sandbox", "detail": "僅簽章 sandbox、入點、退款與重放測試"},
        {"name": "invoice", "status": "disabled", "detail": "正式發票供應商與收款主體待核定"},
        {"name": "storage", "status": "local_private", "detail": "本機私有儲存；獨立 R2 bucket/憑證待啟用"},
        {"name": "stream", "status": "disabled", "detail": "原創文字課程可用；付費影片/字幕/簽章待驗證"},
        {"name": "oidc", "status": "disabled", "detail": "開發 session 可用；正式 IdP 待設定"},
        {"name": "ai", "status": "disabled", "detail": "未將客戶資料傳送外部模型"},
        {"name": "qidaigo", "status": "disconnected", "detail": "唯讀產品彙總來源尚未連線"},
    ]
