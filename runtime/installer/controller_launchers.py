#!/usr/bin/env python3
"""Install controller shortcuts without executing desktop-directory shell syntax.

Called by the product installer only. Existing differing files are always kept.
Directory traversal uses no-follow descriptors, including the user's home path.
"""
import argparse
import os
import pwd
import re
import stat
from pathlib import Path, PurePosixPath

FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
MARKER = 'X-KHPTZ-Controller-Launcher=true\n'


def warn(message):
    print('Warning: controller launcher: ' + message)


def open_directory(path):
    """Open an existing absolute directory, rejecting symlinks in every component."""
    parts = PurePosixPath(path)
    if not parts.is_absolute() or '..' in parts.parts:
        raise ValueError('directory must be absolute without parent traversal')
    fd = os.open('/', FLAGS)
    try:
        for part in parts.parts[1:]:
            child = os.open(part, FLAGS, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except Exception:
        os.close(fd)
        raise


def read_regular(directory, name):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    with os.fdopen(fd, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('expected a regular file')
        data = stream.read(65537)
        if len(data) > 65536:
            raise ValueError('file too large')
        return data.decode('utf-8')


def desktop_path(home):
    """Accept only literal XDG paths; never source, expand shell, or run eval."""
    directory = open_directory(home + '/.config')
    try:
        text = read_regular(directory, 'user-dirs.dirs')
    finally:
        os.close(directory)
    values = re.findall(r'^XDG_DESKTOP_DIR="([^"\n]*)"[ \t]*$', text, re.MULTILINE)
    if len(values) != 1:
        raise ValueError('desktop directory unresolved')
    value = values[0]
    if value == '$HOME' or value == home or value == '$HOME/':
        raise ValueError('desktop disabled')
    if value.startswith('$HOME/'):
        value = home + value[5:]
    if any(char in value for char in '$`\\\r\n'):
        raise ValueError('unsupported desktop path syntax')
    path = PurePosixPath(value)
    root = PurePosixPath(home)
    if not path.is_absolute() or '..' in path.parts or root not in path.parents:
        raise ValueError('desktop directory must be strictly inside home')
    return str(path)


def install_file(directory, name, content, uid, gid, mode):
    """Publish a complete new inode atomically; never replace an existing inode."""
    import secrets
    temporary = '.khptz-launcher-' + secrets.token_hex(12)
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                 0o600, dir_fd=directory)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(content)
            stream.flush()
            os.fchown(stream.fileno(), uid, gid)
            os.fchmod(stream.fileno(), mode)
        try:
            os.link(temporary, name, src_dir_fd=directory, dst_dir_fd=directory,
                    follow_symlinks=False)
        except FileExistsError:
            # Identical files make reruns harmless; differing files need review.
            if read_regular(directory, name) != content:
                warn('existing ' + name + ' preserved; remove it manually to update')
                return False
    finally:
        os.unlink(temporary, dir_fd=directory)
    return True


def launcher(mode):
    command = '/usr/local/libexec/khptz-controller'
    return ('[Desktop Entry]\nType=Application\nName=KH PTZ Control\n'
            'Comment=Start the supervised KHPTZ controller\nExec=' + command + '\n'
            'Icon=video-display\nTerminal=false\nCategories=AudioVideo;System;\n'
            'StartupNotify=false\n' + MARKER)


def install(mode, user):
    content = launcher(mode)
    helper = open_directory('/usr/local/libexec')
    try:
        script = (Path(__file__).resolve().parents[1] / 'khptz-controller.sh').read_text()
        if not install_file(helper, 'khptz-controller', script, 0, 0, 0o755):
            raise ValueError('controller helper conflict; refusing new shortcuts')
    finally:
        os.close(helper)
    menu = open_directory('/usr/share/applications')
    try:
        install_file(menu, 'khptz-controller.desktop', content, 0, 0, 0o644)
    finally:
        os.close(menu)
    if not user:
        warn('wizard user unresolved; desktop shortcut skipped')
        return
    account = pwd.getpwnam(user)
    home = account.pw_dir.rstrip('/')
    if not home or home == '/':
        raise ValueError('invalid wizard home')
    target = desktop_path(home)
    directory = open_directory(target)
    try:
        install_file(directory, 'khptz-controller.desktop', content,
                     account.pw_uid, account.pw_gid, 0o755)
    finally:
        os.close(directory)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('system', 'user'), required=True)
    parser.add_argument('--user', default='')
    args = parser.parse_args()
    try:
        install(args.mode, args.user)
    except (OSError, ValueError, KeyError) as exc:
        warn(str(exc) + '; shortcut installation skipped')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
