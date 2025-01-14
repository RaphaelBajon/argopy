import os
import pytest
import argopy
from argopy.options import OPTIONS
from argopy.errors import OptionValueError, FtpPathError, ErddapPathError
from utils import requires_gdac
from mocked_http import mocked_httpserver, mocked_server_address


def test_invalid_option_name():
    with pytest.raises(ValueError):
        argopy.set_options(not_a_valid_options=True)


def test_opt_src():
    with pytest.raises(OptionValueError):
        argopy.set_options(src="invalid_src")
    with argopy.set_options(src="erddap"):
        assert OPTIONS["src"]


@requires_gdac
def test_opt_gdac_ftp():
    with pytest.raises(FtpPathError):
        argopy.set_options(ftp="invalid_path")

    local_ftp = argopy.tutorial.open_dataset("gdac")[0]
    with argopy.set_options(ftp=local_ftp):
        assert OPTIONS["ftp"] == local_ftp


def test_opt_ifremer_erddap(mocked_httpserver):
    with pytest.raises(ErddapPathError):
        argopy.set_options(erddap="invalid_path")

    with argopy.set_options(erddap=mocked_server_address):
        assert OPTIONS["erddap"] == mocked_server_address


def test_opt_dataset():
    with pytest.raises(OptionValueError):
        argopy.set_options(dataset="invalid_ds")
    with argopy.set_options(dataset="phy"):
        assert OPTIONS["dataset"] == "phy"
    with argopy.set_options(dataset="bgc"):
        assert OPTIONS["dataset"] == "bgc"
    with argopy.set_options(dataset="ref"):
        assert OPTIONS["dataset"] == "ref"


def test_opt_cachedir():
    with pytest.raises(OptionValueError):
        argopy.set_options(cachedir="invalid_path")
    with argopy.set_options(cachedir=os.path.expanduser("~")):
        assert OPTIONS["cachedir"]


def test_opt_mode():
    with pytest.raises(OptionValueError):
        argopy.set_options(mode="invalid_mode")
    with argopy.set_options(mode="standard"):
        assert OPTIONS["mode"]
    with argopy.set_options(mode="expert"):
        assert OPTIONS["mode"]


def test_opt_api_timeout():
    with pytest.raises(OptionValueError):
        argopy.set_options(api_timeout='toto')
    with pytest.raises(OptionValueError):
        argopy.set_options(api_timeout=-12)


def test_opt_trust_env():
    with pytest.raises(ValueError):
        argopy.set_options(trust_env='toto')
    with pytest.raises(ValueError):
        argopy.set_options(trust_env=0)
