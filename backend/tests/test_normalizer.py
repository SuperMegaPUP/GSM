"""Тесты нормализатора данных."""

from app.services.normalizer import (
    FluidNormalizer,
    normalize_years,
    compute_variant_hash,
)


class TestFluidNormalizer:
    def test_extract_viscosity(self):
        vis, rest = FluidNormalizer.extract_viscosity("5W-30 Synthetic")
        assert vis == "5W-30"
        assert rest == "Synthetic"

    def test_extract_viscosity_none(self):
        vis, rest = FluidNormalizer.extract_viscosity("Mobil 1")
        assert vis is None
        assert rest == "Mobil 1"

    def test_extract_brand_gazpromneft(self):
        brand, rest = FluidNormalizer.extract_brand("Gazpromneft Premium 5W-30")
        assert brand == "Gazpromneft"
        assert "Premium" in rest

    def test_extract_brand_mobil(self):
        brand, rest = FluidNormalizer.extract_brand("Mobil 1 ESP")
        assert brand == "Mobil"
        assert rest == "1 ESP"

    def test_extract_brand_lowercase(self):
        brand, rest = FluidNormalizer.extract_brand("castrol Edge")
        assert brand == "Castrol"
        assert rest == "Edge"

    def test_extract_brand_unknown(self):
        brand, rest = FluidNormalizer.extract_brand("Super Oil 5W-30")
        assert brand == "Super"
        assert rest == "Oil 5W-30"

    def test_normalize_with_brand_and_viscosity(self):
        result = FluidNormalizer.normalize(
            fluid_name="Mobil 1 ESP 5W-30",
            viscosity_from_parser="5W-30",
            api_class_from_parser="SN",
            node_type="ENGINE",
        )
        assert result["brand"] == "Mobil"
        assert result["canonical_name"] == "Mobil 1 ESP"
        assert result["viscosity_sae"] == "5W-30"
        assert result["api_class"] == "SN"
        assert result["fluid_type"].value == "engine_oil"

    def test_normalize_without_name(self):
        result = FluidNormalizer.normalize(
            fluid_name=None,
            viscosity_from_parser="75W-90",
            api_class_from_parser="GL-5",
            node_type="REAR_DIFF",
        )
        assert result["canonical_name"] == "Rear Diff Oil 75W-90 (GL-5)"
        assert result["fluid_type"].value == "differential"

    def test_make_hash_consistency(self):
        h1 = FluidNormalizer.make_hash("Mobil", "1 ESP", "5W-30", "SN")
        h2 = FluidNormalizer.make_hash("Mobil", "1 ESP", "5W-30", "SN")
        assert h1 == h2

    def test_make_hash_different(self):
        h1 = FluidNormalizer.make_hash("Mobil", "1 ESP", "5W-30", "SN")
        h2 = FluidNormalizer.make_hash("Castrol", "Edge", "5W-30", "SN")
        assert h1 != h2


class TestNormalizeYears:
    def test_full_range(self):
        start, end = normalize_years("1998.01-2002.10")
        assert start == 1998
        assert end == 2002

    def test_short_years(self):
        start, end = normalize_years("98.01-02.10")
        assert start == 1998
        assert end == 2002

    def test_single_year(self):
        start, end = normalize_years("2005")
        assert start == 2005
        assert end is None

    def test_none(self):
        start, end = normalize_years(None)
        assert start is None
        assert end is None

    def test_empty(self):
        start, end = normalize_years("")
        assert start is None
        assert end is None


class TestComputeVariantHash:
    def test_consistency(self):
        h1 = compute_variant_hash("model_1", "2AZ-FE", "sedan", "2.4")
        h2 = compute_variant_hash("model_1", "2AZ-FE", "sedan", "2.4")
        assert h1 == h2

    def test_different_inputs(self):
        h1 = compute_variant_hash("model_1", "2AZ-FE", "sedan", "2.4")
        h2 = compute_variant_hash("model_1", "2AZ-FE", "sedan", "2.0")
        assert h1 != h2
