import pytest
from tests.fixtures.build_fixture import build

@pytest.fixture(scope="session")
def sample_pdf_path():
    return build()
