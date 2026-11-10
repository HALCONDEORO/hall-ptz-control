"""Splash, Admin and workers must share the effective camera configuration."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest


@pytest.fixture
def camera_ui():
    from conftest import ensure_real_qt
    ensure_real_qt()
    import ui.main_window as mw
    before = [(cam.ip, cam.cam_id, cam.check) for cam in (mw.CAM1, mw.CAM2)]
    yield mw
    for cam, saved in zip((mw.CAM1, mw.CAM2), before):
        cam.ip, cam.cam_id, cam.check = saved


def settings():
    return SimpleNamespace(cameras=[
        SimpleNamespace(role='platform', ip='192.0.2.11', visca_id='81'),
        SimpleNamespace(role='comments', ip='192.0.2.12', visca_id='82'),
    ])


def test_hydrates_shared_objects_before_ui_consumes_them(camera_ui):
    mw = camera_ui
    mw.CAM1.ip = mw.CAM2.ip = ''
    with patch('config.effective.load_effective_config', return_value=settings()), patch('adapters.sim_mode.is_active', return_value=False):
        first, second = mw._load_cam_configs_from_yaml()
    assert first is mw.CAM1
    assert second is mw.CAM2
    assert (mw.CAM1.ip, mw.CAM1.cam_id) == ('192.0.2.11', '81')
    assert (mw.CAM2.ip, mw.CAM2.cam_id) == ('192.0.2.12', '82')


def test_simulation_never_loads_production_camera_settings(camera_ui):
    mw = camera_ui
    mw.CAM1.ip, mw.CAM2.ip = '127.0.0.1', '127.0.0.2'
    with patch('config.effective.load_effective_config') as load, patch('adapters.sim_mode.is_active', return_value=True):
        assert mw._load_cam_configs_from_yaml() == (mw.CAM1, mw.CAM2)
    load.assert_not_called()
    assert mw.CAM1.ip == '127.0.0.1'


def test_unreadable_config_preserves_existing_objects(camera_ui):
    mw = camera_ui
    with patch('config.effective.load_effective_config', side_effect=OSError('unreadable')), patch('adapters.sim_mode.is_active', return_value=False):
        assert mw._load_cam_configs_from_yaml() == (mw.CAM1, mw.CAM2)


def test_reload_updates_previously_imported_references(camera_ui):
    mw = camera_ui
    first_ref, second_ref = mw.CAM1, mw.CAM2
    saved = settings()
    with patch('config.effective.load_effective_config', return_value=saved), patch('adapters.sim_mode.is_active', return_value=False):
        mw._load_cam_configs_from_yaml()
        saved.cameras[1].ip = '192.0.2.22'
        saved.cameras[1].visca_id = '83'
        first, second = mw._load_cam_configs_from_yaml()
    assert first is first_ref
    assert second is second_ref
    assert (second_ref.ip, second_ref.cam_id) == ('192.0.2.22', '83')


def test_reversed_saved_order_hydrates_by_role(camera_ui):
    saved = settings()
    saved.cameras.reverse()
    with patch('config.effective.load_effective_config', return_value=saved), patch('adapters.sim_mode.is_active', return_value=False):
        first, second = camera_ui._load_cam_configs_from_yaml()
    assert first.ip == '192.0.2.11'
    assert second.ip == '192.0.2.12'


def test_missing_platform_does_not_copy_comments_into_platform(camera_ui):
    saved = settings()
    saved.cameras = saved.cameras[1:]
    with patch('config.effective.load_effective_config', return_value=saved), patch('adapters.sim_mode.is_active', return_value=False):
        first, second = camera_ui._load_cam_configs_from_yaml()
    assert first.ip == ''
    assert second.ip == '192.0.2.12'
