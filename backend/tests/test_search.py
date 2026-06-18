"""Тесты поискового движка."""

from uuid import UUID, uuid4
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.search_schemas import CarSearchSchema
from app.services.search_engine import (
    _group_by_node,
    NotFoundError,
)
from app.models.models import (
    CarBrand,
    CarModel,
    CarVariant,
    Fluid,
    Recommendation,
    FluidType,
    NodeType,
)


def _make_fluid(
    id: UUID,
    canonical_name: str = "Test Oil 5W-30",
    brand: str = "Test",
    fluid_type: str = "engine_oil",
    oem_approvals: list | None = None,
) -> Fluid:
    return Fluid(
        id=id,
        canonical_name=canonical_name,
        brand=brand,
        product_line=None,
        viscosity_sae="5W-30",
        api_class="SN",
        acea_class=None,
        oem_approvals=oem_approvals or [],
        fluid_type=FluidType(fluid_type),
        company_id=uuid4(),
        hash_signature="",
    )


def _make_recommendation(
    fluid_id: UUID,
    fluid: Fluid | None = None,
    node_type: str = "ENGINE",
    is_oem: bool = False,
    volume: float | None = None,
    confidence: float | None = None,
) -> Recommendation:
    rec = Recommendation(
        id=uuid4(),
        car_variant_id=uuid4(),
        fluid_id=fluid_id,
        node_type=NodeType(node_type),
        is_oem_recommendation=is_oem,
        volume_liters=volume,
        volume_with_filter=None,
        oem_specification=None,
        confidence_score=confidence,
        source=None,
        company_id=uuid4(),
    )
    if fluid:
        rec.fluid = fluid
    return rec


class TestGroupByNode:
    def test_single_fluid_single_node(self):
        fluid_id = uuid4()
        fluid = _make_fluid(fluid_id)
        recs = [_make_recommendation(fluid_id, fluid, "ENGINE")]
        groups = _group_by_node(recs)
        assert len(groups) == 1
        assert groups[0].node_type == "ENGINE"
        assert len(groups[0].recommendations) == 1

    def test_dedup_same_fluid_same_node(self):
        fluid_id = uuid4()
        fluid = _make_fluid(fluid_id)
        recs = [
            _make_recommendation(fluid_id, fluid, "ENGINE"),
            _make_recommendation(fluid_id, fluid, "ENGINE"),
        ]
        groups = _group_by_node(recs)
        assert len(groups) == 1
        assert len(groups[0].recommendations) == 1

    def test_same_fluid_different_nodes(self):
        fluid_id = uuid4()
        fluid = _make_fluid(fluid_id)
        recs = [
            _make_recommendation(fluid_id, fluid, "ENGINE"),
            _make_recommendation(fluid_id, fluid, "AUTO_TRANSMISSION"),
        ]
        groups = _group_by_node(recs)
        assert len(groups) == 2

    def test_different_fluids_same_node(self):
        f1 = _make_fluid(uuid4(), "Oil A")
        f2 = _make_fluid(uuid4(), "Oil B")
        recs = [
            _make_recommendation(f1.id, f1, "ENGINE"),
            _make_recommendation(f2.id, f2, "ENGINE"),
        ]
        groups = _group_by_node(recs)
        assert len(groups) == 1
        assert len(groups[0].recommendations) == 2

    def test_oem_flag_preserved(self):
        fluid_id = uuid4()
        fluid = _make_fluid(fluid_id)
        recs = [_make_recommendation(fluid_id, fluid, "ENGINE", is_oem=True)]
        groups = _group_by_node(recs)
        assert groups[0].recommendations[0].is_oem_recommendation is True

    def test_empty_list(self):
        groups = _group_by_node([])
        assert groups == []

    def test_node_label_contains_russian(self):
        fluid_id = uuid4()
        fluid = _make_fluid(fluid_id)
        recs = [_make_recommendation(fluid_id, fluid, "ENGINE")]
        groups = _group_by_node(recs)
        assert groups[0].node_label == "Двигатель"
