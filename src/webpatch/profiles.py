"""Explicit PHP deployment profiles; vendor advisories remain separate."""
PHP_PROFILES={
    ('ubuntu','22.04','jammy'):'php8.1',
    ('ubuntu','24.04','noble'):'php8.3',
    ('debian','12','bookworm'):'php8.2',
    ('debian','13','trixie'):'php8.4',
}


def php_source_profile(environment):
    return PHP_PROFILES.get((environment.os_id,environment.version_id,environment.codename))
