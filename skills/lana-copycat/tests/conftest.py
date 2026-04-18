import pytest


# make pytest-asyncio use auto mode so @pytest.mark.asyncio isn't needed on every test
def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: mark test as async")
