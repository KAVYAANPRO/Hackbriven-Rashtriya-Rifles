from __future__ import annotations

from dataclasses import dataclass

from backend.models.schemas import MotionTier

"""Plans and top-up packs - the single source of truth the frontend reads via
GET /plans. A plan gates which motion tiers an account may run (real
generative motion spends third-party credits, so only paid plans get it) and
carries the credits it grants. A paid plan lasts `period_days`, then the
account falls back to Free; credits already granted never expire."""

ALL_TIERS = (MotionTier.BASIC, MotionTier.BALANCED, MotionTier.MAX)


@dataclass(frozen=True)
class Resolution:
    id: str
    label: str
    width: int
    height: int
    credit_surcharge: int  # extra credits on top of the motion tier's price

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "width": self.width,
            "height": self.height,
            "credit_surcharge": self.credit_surcharge,
        }


# The pipeline always composes at 1080x1920; "720p" is a scaled-down delivery and
# "4k" is an enhanced up-scale of that master, which costs real compute/money, so it
# carries a surcharge and is limited to paid plans.
RESOLUTIONS: tuple[Resolution, ...] = (
    Resolution("720p", "720p", 720, 1280, 0),
    Resolution("1080p", "1080p", 1080, 1920, 0),
    Resolution("4k", "4K", 2160, 3840, 3),
)
# Must stay a resolution every plan (including Free) can use, since it's the
# fallback when a job doesn't specify one - Free no longer includes 1080p,
# so 720p is the only choice that never needs a plan upgrade just to omit
# the field.
DEFAULT_RESOLUTION = "720p"
_RES_BY_ID = {r.id: r for r in RESOLUTIONS}


@dataclass(frozen=True)
class PlanDef:
    id: str
    name: str
    price_paise: int  # INR x100; 0 = free
    credits: int  # granted on purchase (free: granted once at signup via settings.signup_credits)
    period_days: int | None  # None = never expires
    tiers: tuple[MotionTier, ...]
    resolutions: tuple[str, ...] = ("720p",)
    perks: tuple[str, ...] = ()  # extra marketing/behavioral notes shown on the plan card, e.g. queue priority

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "price_paise": self.price_paise,
            "credits": self.credits,
            "period_days": self.period_days,
            "tiers": [t.value for t in self.tiers],
            "resolutions": list(self.resolutions),
            "perks": list(self.perks),
        }


FREE_PLAN_ID = "free"

# Resolution access is tiered: Free is capped at 720p, Pro adds 1080p, and 4K
# (an upscaled, compute-costly master) is a Studio exclusive - previously Pro
# and Studio both listed every resolution including 4k, which gave away the
# Studio-exclusive perk for free at the Pro price.
PLANS: tuple[PlanDef, ...] = (
    PlanDef("free", "Free", 0, 0, None, (MotionTier.BASIC,), ("720p",)),
    PlanDef("pro", "Pro", 49900, 120, 30, ALL_TIERS, ("720p", "1080p")),
    PlanDef(
        "studio", "Studio", 99900, 300, 30, ALL_TIERS, ("720p", "1080p", "4k"),
        perks=("During high-traffic periods, Studio jobs are given processing priority.",),
    ),
)

# One-off credit packs (id is the position, stable because the list is append-only).
PACKS: tuple[dict, ...] = (
    {"id": 0, "credits": 20, "price_paise": 19900},
    {"id": 1, "credits": 60, "price_paise": 49900},
    {"id": 2, "credits": 150, "price_paise": 99900},
)


def plan_def(plan_id: str) -> PlanDef | None:
    return next((p for p in PLANS if p.id == plan_id), None)


def pack_def(pack_id: int) -> dict | None:
    return next((p for p in PACKS if p["id"] == pack_id), None)


def tiers_for(plan_id: str) -> list[str]:
    plan = plan_def(plan_id) or plan_def(FREE_PLAN_ID)
    return [t.value for t in plan.tiers]


def can_use(plan_id: str, tier: MotionTier) -> bool:
    plan = plan_def(plan_id) or plan_def(FREE_PLAN_ID)
    return tier in plan.tiers


def cheapest_plan_for(tier: MotionTier) -> PlanDef | None:
    return next((p for p in PLANS if tier in p.tiers), None)


def resolution_def(resolution_id: str) -> Resolution | None:
    return _RES_BY_ID.get(resolution_id)


def resolutions_for(plan_id: str) -> list[str]:
    plan = plan_def(plan_id) or plan_def(FREE_PLAN_ID)
    return list(plan.resolutions)


def can_use_resolution(plan_id: str, resolution_id: str) -> bool:
    return resolution_id in resolutions_for(plan_id)


def cheapest_plan_for_resolution(resolution_id: str) -> PlanDef | None:
    return next((p for p in PLANS if resolution_id in p.resolutions), None)
