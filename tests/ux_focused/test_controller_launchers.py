"""Inert, stdlib-only checks: no installer or real service commands run."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('launchers', ROOT / 'runtime/installer/controller_launchers.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class LaunchersTest(unittest.TestCase):
    def test_xdg_localized_disabled_and_injection(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            home = Path(tmp)
            (home / '.config').mkdir()
            config = home / '.config/user-dirs.dirs'
            for value in ('$HOME/Escritorio', str(home / 'Bureau')):
                config.write_text('XDG_DESKTOP_DIR="' + value + '"\n')
                self.assertIn(m.desktop_path(str(home)), [str(home / 'Escritorio'), str(home / 'Bureau')])
            for value in ('$HOME', '$HOME/', '/tmp/outside', '$HOME/../escape',
                          '$(touch forbidden)', '$HOME/`id`', '$HOME/escaped\\name'):
                config.write_text('XDG_DESKTOP_DIR="' + value + '"\n')
                with self.assertRaises(ValueError):
                    m.desktop_path(str(home))
            config.write_text('# no desktop configured\n')
            with self.assertRaises(ValueError):
                m.desktop_path(str(home))
            config.unlink()
            with self.assertRaises(OSError):
                m.desktop_path(str(home))

    def test_exclusive_install_modes_idempotence_and_preservation(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            fd = m.open_directory(tmp)
            try:
                content = m.launcher('system')
                m.install_file(fd, 'controller.desktop', content, os.getuid(), os.getgid(), 0o755)
                target = Path(tmp) / 'controller.desktop'
                inode = target.stat().st_ino
                self.assertEqual(target.stat().st_mode & 0o777, 0o755)
                self.assertEqual(target.stat().st_uid, os.getuid())
                self.assertEqual(target.stat().st_gid, os.getgid())
                m.install_file(fd, 'controller.desktop', content, os.getuid(), os.getgid(), 0o755)
                self.assertEqual(target.stat().st_ino, inode)
                target.write_text('unrelated user launcher')
                m.install_file(fd, 'controller.desktop', content, os.getuid(), os.getgid(), 0o755)
                self.assertEqual(target.read_text(), 'unrelated user launcher')
                target.unlink()
                target.symlink_to('missing-outside')
                with self.assertRaises(OSError):
                    m.install_file(fd, 'controller.desktop', content, os.getuid(), os.getgid(), 0o755)
                self.assertTrue(target.is_symlink())
                self.assertFalse((Path(tmp) / 'missing-outside').exists())
                self.assertEqual(list(Path(tmp).glob('.khptz-launcher-*')), [])
            finally:
                os.close(fd)

    def test_no_directory_symlinks(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            home = Path(tmp)
            (home / 'real').mkdir()
            (home / 'link').symlink_to(home / 'real', target_is_directory=True)
            with self.assertRaises(OSError):
                m.open_directory(str(home / 'link'))
            with self.assertRaises(ValueError):
                m.open_directory(str(home / '../elsewhere'))

    def test_installer_product_only_and_stable_mode_switch(self):
        script = (ROOT / 'runtime/installer/install.sh').read_text()
        block = script[script.index('# Controller shortcuts share'):script.index('# ── Install state')]
        self.assertIn('if [[ "${DEV_MODE}" == "false" ]]', block)
        self.assertIn('--mode "${GUI_MODE}" --user "${WIZARD_USER}"', block)
        self.assertIn('install -d -m 755 /usr/local/libexec', block)
        self.assertEqual(m.launcher('system'), m.launcher('user'))
        self.assertNotIn('main.py', m.launcher('system'))

    def test_resolved_user_menu_and_localized_desktop(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            home = root / 'home'
            menu = root / 'applications'
            menu.mkdir()
            libexec = root / 'libexec'
            libexec.mkdir()
            (home / '.config').mkdir(parents=True)
            (home / 'Escritorio').mkdir()
            config = home / '.config/user-dirs.dirs'
            config.write_text('XDG_DESKTOP_DIR="$HOME/Escritorio"\n')
            account = SimpleNamespace(pw_dir=str(home), pw_uid=os.getuid(), pw_gid=os.getgid())
            original_open = m.open_directory
            def redirected(path):
                return original_open(str(menu) if path == '/usr/share/applications' else str(libexec) if path == '/usr/local/libexec' else path)
            original_install = m.install_file
            def unprivileged(directory, name, content, uid, gid, mode):
                return original_install(directory, name, content, os.getuid(), os.getgid(), mode)
            with patch.object(m, 'open_directory', side_effect=redirected), \
                 patch.object(m.pwd, 'getpwnam', return_value=account), \
                 patch.object(m, 'install_file', side_effect=unprivileged) as writes:
                m.install('system', 'synthetic-user')
                self.assertEqual(writes.call_args_list[1].args[-3:], (0, 0, 0o644))
                self.assertEqual(writes.call_args_list[2].args[-3:], (os.getuid(), os.getgid(), 0o755))
                desktop = home / 'Escritorio/khptz-controller.desktop'
                inode = desktop.stat().st_ino
                m.install('user', 'synthetic-user')
                self.assertEqual(desktop.stat().st_ino, inode)
                self.assertEqual((menu / desktop.name).stat().st_mode & 0o777, 0o644)
                config.write_text('XDG_DESKTOP_DIR="$HOME"\n')
                with self.assertRaises(ValueError):
                    m.install('user', 'synthetic-user')
                self.assertTrue(desktop.exists())

    def test_launch_commands_inert(self):
        template = (ROOT / 'runtime/khptz-controller.sh').read_text()
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            tmp = Path(tmp)
            systemctl = tmp / 'systemctl'
            session = tmp / 'session'
            log = tmp / 'calls'
            systemctl.write_text('#!/bin/bash\necho "$*" >> "$CALLS"\nif [[ "$1" == is-active ]]; then exit "${ACTIVE_STATUS}"; fi\nexit "${START_STATUS:-0}"\n')
            session.write_text('#!/bin/bash\necho session >> "$CALLS"\n')
            systemctl.chmod(0o755)
            session.chmod(0o755)
            for mode, status, expected in [
                ('system', '0', ['--no-ask-password --no-block start khptz-control.service']),
                ('user', '0', ['is-active --quiet khptz-control.service']),
                ('user', '3', ['is-active --quiet khptz-control.service', 'session']),
            ]:
                log.unlink(missing_ok=True)
                script = template.replace('[[ -f /usr/local/libexec/khptz-gui-session ]]', '[[ ' + mode + ' == user ]]').replace('/usr/bin/systemctl', str(systemctl)).replace('/usr/local/libexec/khptz-gui-session', str(session))
                subprocess.run(['bash', '-c', script], env={**os.environ, 'CALLS': str(log), 'ACTIVE_STATUS': status}, check=True)
                self.assertEqual(log.read_text().splitlines(), expected)
            log.unlink()
            script = template.replace('[[ -f /usr/local/libexec/khptz-gui-session ]]', '[[ system == user ]]').replace('/usr/bin/systemctl', str(systemctl))
            denied = subprocess.run(['bash', '-c', script], env={**os.environ, 'CALLS': str(log), 'ACTIVE_STATUS': '3', 'START_STATUS': '1'})
            self.assertEqual(denied.returncode, 1)
            self.assertEqual(log.read_text().splitlines(), ['--no-ask-password --no-block start khptz-control.service'])


if __name__ == '__main__':
    unittest.main()
