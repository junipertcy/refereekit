import pytest
from tests.fixtures.build_fixture import build

@pytest.fixture(scope="session")
def sample_pdf_path():
    return build()

@pytest.fixture(scope="session")
def sample_doc(sample_pdf_path):
    from refereekit.ingest import ingest
    return ingest(sample_pdf_path)
