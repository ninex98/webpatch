import pytest

from conftest import FakeSystem, NOW
from webpatch.discovery import AptAdapter, PhpHintsAdapter
from webpatch.runtime import RuntimeAdapter, start_ticks
from webpatch.configuration import ConfigurationAdapter
from webpatch.service import scan
from webpatch.system import CommandResult, ProbeError, service_command, LocalSystem


def runtime_fixture(apache=False):
    name = "libapache2-mod-php8.1" if apache else "php8.1-fpm"
    path = "/usr/sbin/apache2" if apache else "/usr/sbin/php-fpm8.1"
    fake = FakeSystem({"packages": [[name, "8.1.2-1ubuntu2.28", "amd64", "php8.1", "8.1.2-1ubuntu2.28", "install ok installed"]],
                       "processes": [{"pid": 42, "comm": "apache2" if apache else "php-fpm8.1", "exe": path}]})
    fake.reads["/proc/42/stat"] = "42 (name (with spaces)) S " + "0 " * 18 + "123 0"
    fake.links["/proc/42/ns/pid"] = "pid:[1]"
    fake.links["/proc/42/ns/net"] = "net:[1]"
    fake.dirs["/proc/42/fd"] = ["8"]
    fake.links["/proc/42/fd/8"] = "socket:[1234]"
    fake.reads["/proc/42/net/unix"] = "Num RefCount Protocol Flags Type St Inode Path\n000: 00000002 00000000 00010000 0001 01 1234 /run/php/php8.1-fpm.sock\n"
    fake.reads["/proc/42/maps"] = f"100-200 r-xp 00000000 00:01 5 {path}\n"
    fake.identities["/proc/42/root"] = fake.identities["/"]
    identity = {"device": 1, "inode": 5, "size": 10, "sha256": "a" * 64}
    fake.fingerprints.update({"/proc/42/exe": identity, path: identity})
    fake.commands[("/usr/bin/dpkg-query", "-S", path)] = CommandResult(0, f"{'apache2-bin' if apache else name}: {path}\n")
    unit = "apache2.service" if apache else "php8.1-fpm.service"
    fake.reads["/proc/42/cgroup"] = f"0::/system.slice/{unit}\n"
    fake.commands[service_command(unit)] = CommandResult(0, f"Id={unit}\nLoadState=loaded\nActiveState=active\nSubState=running\nMainPID=42\nControlGroup=/system.slice/{unit}\nFragmentPath=/lib/systemd/system/{unit}\n")
    if apache:
        module = "/usr/lib/apache2/modules/libphp8.1.so"
        fake.reads["/proc/42/maps"] = f"100-200 r-xp 00000000 00:01 5 {module}\n"
        fake.fingerprints[module] = identity
        fake.commands[("/usr/bin/dpkg-query", "-S", module)] = CommandResult(0, f"{name}: {module}\n")
    return fake


def report(fake):
    return scan(fake, now=NOW, adapters=(AptAdapter(), PhpHintsAdapter(), RuntimeAdapter()))


@pytest.mark.parametrize("apache", [False, True])
def test_local_service_correlation_is_not_patch_or_origin_verdict(apache):
    result = report(runtime_fixture(apache))
    runtime = result.inventory.runtimes[0]
    assert runtime.association == "VERIFIED_LOCAL_ASSOCIATION"
    assert runtime.package_ids == (("libapache2-mod-php8.1" if apache else "php8.1-fpm") + ":amd64",)
    assert runtime.start_ticks == "123"
    assert result.safe is False
    assert all(a.runtime_status == "UNKNOWN" for a in result.assessments)


@pytest.mark.parametrize("change,expected", [
    ("deleted", "DELETED_RUNNING_IMAGE"),
    ("namespace", "FOREIGN_OR_UNKNOWN_MOUNT_NAMESPACE"),
    ("pidnamespace", "PID_NAMESPACE_OR_ROOT_UNVERIFIED"),
    ("chroot", "PID_NAMESPACE_OR_ROOT_UNVERIFIED"),
    ("replaced", "LOADED_EXECUTABLE_DIFFERS_OR_UNREADABLE"),
    ("permission", "LOADED_EXECUTABLE_DIFFERS_OR_UNREADABLE"),
    ("inactive", "SYSTEMD_SERVICE_UNVERIFIED"),
    ("cgroup", "SYSTEMD_SERVICE_UNVERIFIED"),
    ("owner", "PACKAGE_OWNERSHIP_UNVERIFIED"),
    ("stat", "PROCESS_START_ID_UNREADABLE"),
])
def test_identity_failure_matrix(change, expected):
    fake = runtime_fixture()
    if change == "deleted": fake.links["/proc/42/exe"] += " (deleted)"
    if change == "namespace":
        fake.links["/proc/42/ns/mnt"] = "mnt:[2]"
        fake.reads["/proc/42/cgroup"] = "0::/docker/container"
    if change == "pidnamespace": fake.links["/proc/42/ns/pid"] = "pid:[2]"
    if change == "chroot": fake.identities["/proc/42/root"] = {"device": 1, "inode": 2}
    if change == "replaced": fake.fingerprints["/proc/42/exe"] = {"device": 1, "inode": 6, "sha256": "b" * 64}
    if change == "permission": fake.fingerprints["/proc/42/exe"] = ProbeError("PermissionError")
    if change == "inactive": fake.commands[service_command("php8.1-fpm.service")] = CommandResult(0, "ActiveState=inactive\n")
    if change == "cgroup": fake.reads["/proc/42/cgroup"] = "0::/system.slice/unrelated.service\n"
    if change == "owner": fake.commands[("/usr/bin/dpkg-query", "-S", "/usr/sbin/php-fpm8.1")] = CommandResult(0, "diversion by local: /usr/sbin/php-fpm8.1\n")
    if change == "stat": fake.reads["/proc/42/stat"] = ProbeError("FileNotFoundError")
    result = report(fake).inventory.runtimes[0]
    assert result.association == "UNKNOWN"
    assert expected in result.blockers
    if change in {"namespace", "pidnamespace", "chroot", "deleted"}:
        assert not any(op == "fingerprint" for op, _ in fake.calls)


def test_pid_reuse_is_detected():
    fake = runtime_fixture()
    read = fake.read_text
    counter = 0
    def reuse(path):
        nonlocal counter
        result = read(path)
        if path == "/proc/42/stat":
            counter += 1
            if counter == 2: return result.replace("123", "456")
        return result
    fake.read_text = reuse
    assert "PROCESS_CHANGED_DURING_SCAN" in report(fake).inventory.runtimes[0].blockers


@pytest.mark.parametrize("same_file", [True, False])
def test_systemd_private_namespace_requires_identical_file_view(same_file):
    fake = runtime_fixture()
    fake.links["/proc/42/ns/mnt"] = "mnt:[2]"
    fake.fingerprints["/proc/42/root/usr/sbin/php-fpm8.1"] = (
        fake.fingerprints["/usr/sbin/php-fpm8.1"] if same_file else {"inode": 99})
    runtime = report(fake).inventory.runtimes[0]
    assert (runtime.association == "VERIFIED_LOCAL_ASSOCIATION") is same_file


@pytest.mark.parametrize("mutation", ["deleted", "inode", "permission", "absent"])
def test_modphp_is_verified_from_loaded_mapping(mutation):
    fake = runtime_fixture(True)
    if mutation == "deleted": fake.reads["/proc/42/maps"] = fake.reads["/proc/42/maps"].rstrip() + " (deleted)\n"
    if mutation == "inode": fake.reads["/proc/42/maps"] = fake.reads["/proc/42/maps"].replace("00:01 5", "00:01 7")
    if mutation == "permission": fake.reads["/proc/42/maps"] = ProbeError("PermissionError")
    if mutation == "absent": fake.reads["/proc/42/maps"] = ""
    assert report(fake).inventory.runtimes[0].association == "UNKNOWN"


def test_fpm_pool_and_static_nginx_relation():
    fake = runtime_fixture()
    root = "/etc/php/8.1/fpm"
    fake.reads[root + "/php-fpm.conf"] = "[global]\ninclude=/etc/php/8.1/fpm/pool.d/*.conf\n"
    fake.dirs[root + "/pool.d"] = ["www.conf"]
    fake.reads[root + "/pool.d/www.conf"] = "[www]\nlisten=/run/php/php8.1-fpm.sock\n"
    fake.reads[root + "/php.ini"] = "; fixture\n"
    fake.dirs[root + "/conf.d"] = []
    fake.reads["/etc/nginx/nginx.conf"] = "http {\nfastcgi_pass unix:/run/php/php8.1-fpm.sock;\n}\n"
    result = scan(fake, now=NOW)
    assert {r.kind for r in result.inventory.config_relations} == {"fpm_pool", "configured_web_handler"}
    assert "HTTP_ROUTING_AND_OVERRIDES_REQUIRE_APPLICATION_PROBE" in result.inventory.coverage_gaps
    assert not result.safe


@pytest.mark.parametrize("target", ["/etc/passwd", "$config/*.conf", "php-fpm.conf"])
def test_includes_outside_scope_dynamic_and_cycle_are_gaps(target):
    fake = runtime_fixture()
    fake.reads["/etc/php/8.1/fpm/php-fpm.conf"] = "include=" + target
    result = scan(fake, now=NOW)
    assert any("CONFIG_" in g for g in result.inventory.coverage_gaps)
    assert ("read_text", "/etc/passwd") not in fake.calls


def test_regular_file_fingerprint_and_replacement(tmp_path):
    path = tmp_path / "binary"
    path.write_bytes(b"fixture bytes")
    system = LocalSystem()
    first = system.fingerprint(str(path))
    other = tmp_path / "new"
    other.write_bytes(b"fixture bytes")
    other.replace(path)
    second = system.fingerprint(str(path))
    assert first["sha256"] == second["sha256"] and first["inode"] != second["inode"]


def test_malformed_stat():
    assert start_ticks("broken") is None
