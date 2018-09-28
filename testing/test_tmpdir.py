from __future__ import absolute_import, division, print_function
import sys
import py
import pytest


def test_tmpdir_fixture(testdir):
    p = testdir.copy_example("tmpdir/tmpdir_fixture.py")
    results = testdir.runpytest(p)
    results.stdout.fnmatch_lines("*1 passed*")


def test_ensuretemp(recwarn):
    d1 = pytest.ensuretemp("hello")
    d2 = pytest.ensuretemp("hello")
    assert d1 == d2
    assert d1.check(dir=1)


class TestTempdirHandler(object):
    def test_mktemp(self, testdir):
        from _pytest.tmpdir import TempdirFactory, TempPathFactory

        config = testdir.parseconfig()
        config.option.basetemp = testdir.mkdir("hello")
        t = TempdirFactory(TempPathFactory.from_config(config))
        tmp = t.mktemp("world")
        assert tmp.relto(t.getbasetemp()) == "world0"
        tmp = t.mktemp("this")
        assert tmp.relto(t.getbasetemp()).startswith("this")
        tmp2 = t.mktemp("this")
        assert tmp2.relto(t.getbasetemp()).startswith("this")
        assert tmp2 != tmp


class TestConfigTmpdir(object):
    def test_getbasetemp_custom_removes_old(self, testdir):
        mytemp = testdir.tmpdir.join("xyz")
        p = testdir.makepyfile(
            """
            def test_1(tmpdir):
                pass
        """
        )
        testdir.runpytest(p, "--basetemp=%s" % mytemp)
        mytemp.check()
        mytemp.ensure("hello")

        testdir.runpytest(p, "--basetemp=%s" % mytemp)
        mytemp.check()
        assert not mytemp.join("hello").check()


def test_basetemp(testdir):
    mytemp = testdir.tmpdir.mkdir("mytemp")
    p = testdir.makepyfile(
        """
        import pytest
        def test_1():
            pytest.ensuretemp("hello")
    """
    )
    result = testdir.runpytest(p, "--basetemp=%s" % mytemp)
    assert result.ret == 0
    assert mytemp.join("hello").check()


@pytest.mark.skipif(
    not hasattr(py.path.local, "mksymlinkto"),
    reason="symlink not available on this platform",
)
def test_tmpdir_always_is_realpath(testdir):
    # the reason why tmpdir should be a realpath is that
    # when you cd to it and do "os.getcwd()" you will anyway
    # get the realpath.  Using the symlinked path can thus
    # easily result in path-inequality
    # XXX if that proves to be a problem, consider using
    # os.environ["PWD"]
    realtemp = testdir.tmpdir.mkdir("myrealtemp")
    linktemp = testdir.tmpdir.join("symlinktemp")
    linktemp.mksymlinkto(realtemp)
    p = testdir.makepyfile(
        """
        def test_1(tmpdir):
            import os
            assert os.path.realpath(str(tmpdir)) == str(tmpdir)
    """
    )
    result = testdir.runpytest("-s", p, "--basetemp=%s/bt" % linktemp)
    assert not result.ret


def test_tmpdir_too_long_on_parametrization(testdir):
    testdir.makepyfile(
        """
        import pytest
        @pytest.mark.parametrize("arg", ["1"*1000])
        def test_some(arg, tmpdir):
            tmpdir.ensure("hello")
    """
    )
    reprec = testdir.inline_run()
    reprec.assertoutcome(passed=1)


def test_tmpdir_factory(testdir):
    testdir.makepyfile(
        """
        import pytest
        @pytest.fixture(scope='session')
        def session_dir(tmpdir_factory):
            return tmpdir_factory.mktemp('data', numbered=False)
        def test_some(session_dir):
            assert session_dir.isdir()
    """
    )
    reprec = testdir.inline_run()
    reprec.assertoutcome(passed=1)


def test_tmpdir_fallback_tox_env(testdir, monkeypatch):
    """Test that tmpdir works even if environment variables required by getpass
    module are missing (#1010).
    """
    monkeypatch.delenv("USER", raising=False)
    monkeypatch.delenv("USERNAME", raising=False)
    testdir.makepyfile(
        """
        import pytest
        def test_some(tmpdir):
            assert tmpdir.isdir()
    """
    )
    reprec = testdir.inline_run()
    reprec.assertoutcome(passed=1)


@pytest.fixture
def break_getuser(monkeypatch):
    monkeypatch.setattr("os.getuid", lambda: -1)
    # taken from python 2.7/3.4
    for envvar in ("LOGNAME", "USER", "LNAME", "USERNAME"):
        monkeypatch.delenv(envvar, raising=False)


@pytest.mark.skip(reason="creates random tmpdirs as part of a system level test")
@pytest.mark.usefixtures("break_getuser")
@pytest.mark.skipif(sys.platform.startswith("win"), reason="no os.getuid on windows")
def test_tmpdir_fallback_uid_not_found(testdir):
    """Test that tmpdir works even if the current process's user id does not
    correspond to a valid user.
    """

    testdir.makepyfile(
        """
        import pytest
        def test_some(tmpdir):
            assert tmpdir.isdir()
    """
    )
    reprec = testdir.inline_run()
    reprec.assertoutcome(passed=1)


@pytest.mark.skip(reason="creates random tmpdirs as part of a system level test")
@pytest.mark.usefixtures("break_getuser")
@pytest.mark.skipif(sys.platform.startswith("win"), reason="no os.getuid on windows")
def test_get_user_uid_not_found():
    """Test that get_user() function works even if the current process's
    user id does not correspond to a valid user (e.g. running pytest in a
    Docker container with 'docker run -u'.
    """
    from _pytest.tmpdir import get_user

    assert get_user() is None


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="win only")
def test_get_user(monkeypatch):
    """Test that get_user() function works even if environment variables
    required by getpass module are missing from the environment on Windows
    (#1010).
    """
    from _pytest.tmpdir import get_user

    monkeypatch.delenv("USER", raising=False)
    monkeypatch.delenv("USERNAME", raising=False)
    assert get_user() is None


class TestNumberedDir(object):
    PREFIX = "fun-"

    def test_make(self, tmp_path):
        from _pytest.tmpdir import make_numbered_dir

        for i in range(10):
            d = make_numbered_dir(root=tmp_path, prefix=self.PREFIX)
            assert d.name.startswith(self.PREFIX)
            assert d.name.endswith(str(i))

    def test_cleanup_lock_create(self, tmp_path):
        d = tmp_path.joinpath("test")
        d.mkdir()
        from _pytest.tmpdir import create_cleanup_lock

        lockfile = create_cleanup_lock(d)
        with pytest.raises(EnvironmentError, match="cannot create lockfile in .*"):
            create_cleanup_lock(d)

        lockfile.unlink()

    def test_lock_register_cleanup_removal(self, tmp_path):
        from _pytest.tmpdir import create_cleanup_lock, register_cleanup_lock_removal

        lock = create_cleanup_lock(tmp_path)

        registry = []
        register_cleanup_lock_removal(lock, register=registry.append)

        cleanup_func, = registry

        assert lock.is_file()

        cleanup_func(original_pid="intentionally_different")

        assert lock.is_file()

        cleanup_func()

        assert not lock.exists()

        cleanup_func()

        assert not lock.exists()

    def test_cleanup_keep(self, tmp_path):
        self.test_make(tmp_path)
        from _pytest.tmpdir import cleanup_numbered_dir

        cleanup_numbered_dir(
            root=tmp_path,
            prefix=self.PREFIX,
            keep=2,
            consider_lock_dead_if_created_before=0,
        )
        a, b = tmp_path.iterdir()
        print(a, b)

    def test_cleanup_locked(self, tmp_path):

        from _pytest import tmpdir

        p = tmpdir.make_numbered_dir(root=tmp_path, prefix=self.PREFIX)

        tmpdir.create_cleanup_lock(p)

        assert not tmpdir.ensure_deletable(
            p, consider_lock_dead_if_created_before=p.stat().st_mtime - 1
        )
        assert tmpdir.ensure_deletable(
            p, consider_lock_dead_if_created_before=p.stat().st_mtime + 1
        )
