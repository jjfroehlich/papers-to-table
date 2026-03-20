import os

import pytest

from backend.app.provider import LMStudioProvider, ProviderError
from backend.app.models import ProviderSettings

pytestmark = pytest.mark.skipif(os.getenv('LMSTUDIO_SMOKE') != '1', reason='Set LMSTUDIO_SMOKE=1 to enable live LM Studio smoke tests')


def test_live_lmstudio_smoke():
    provider = LMStudioProvider(ProviderSettings(provider='lmstudio', model=os.getenv('LMSTUDIO_MODEL', 'local-model')))
    response = provider.invoke({'task': 'smoke', 'retrieval_context': [], 'column_name': 'Smoke'})
    assert isinstance(response.payload, dict)
