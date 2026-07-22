# tests/test_fixture_builds.py
def test_fixture_pdf_builds(sample_pdf_path):
    assert sample_pdf_path.exists()
    assert sample_pdf_path.suffix == ".pdf"
    assert sample_pdf_path.stat().st_size > 1000
