import pandas as pd
import pytest

from atm_engine.config import config_for
from atm_engine.data.synthetic import SyntheticSpec, generate


@pytest.fixture(scope="session")
def cfg():
    return config_for("NQ")


@pytest.fixture(scope="session")
def bars(cfg) -> pd.DataFrame:
    return generate(SyntheticSpec(sessions=4, seed=123), cfg.session)
